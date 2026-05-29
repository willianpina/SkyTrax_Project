"""Aviation MDM — canonical slug, identity resolution, merge policy, collision recovery.

Enterprise identity layer for airline_metadata.slug (unique): prevents blind INSERTs under
sessions with autoflush=False and reconciles semantic duplicates via IATA/ICAO/slug aliases.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from aviation.master_data.normalize import normalize_airline_slug
from aviation.master_data.sources import OpenFlightsAirline
from database.models.aviation import AirlineMetadata

logger = logging.getLogger(__name__)


def canonical_airline_slug(name: str) -> str:
    """Deterministic slug for canonical identity (delegates + minor suffix collapse)."""
    return normalize_airline_slug(name)


def normalize_iata(iata: str | None) -> str | None:
    if not iata or str(iata).strip() in ("-", "\\N", ""):
        return None
    i = str(iata).strip().upper()
    return i if len(i) == 2 else None


def normalize_icao(icao: str | None) -> str | None:
    if not icao or str(icao).strip() in ("-", "\\N", ""):
        return None
    c = str(icao).strip().upper()
    return c if 2 <= len(c) <= 4 else None


def merge_raw_metadata(existing: dict[str, Any] | None, patch: dict[str, Any]) -> dict[str, Any]:
    base = dict(existing or {})
    for k, v in (patch or {}).items():
        if v is None:
            continue
        prev = base.get(k)
        if isinstance(prev, dict) and isinstance(v, dict):
            prev.update(v)
            base[k] = prev
        else:
            base[k] = v
    return base


def build_airline_slug_lookup(session: Session) -> dict[str, AirlineMetadata]:
    """Load all airline_metadata rows indexed by slug (authoritative uniqueness key)."""
    rows = session.scalars(select(AirlineMetadata)).all()
    return {m.slug: m for m in rows}


def semantic_airline_lookup(
    session: Session,
    slug: str,
    iata: str | None,
    icao: str | None,
    slug_lookup: dict[str, AirlineMetadata],
    *,
    name_norm_hint: str | None = None,
) -> AirlineMetadata | None:
    """Secondary resolution when slug miss: IATA, ICAO, normalized_name."""
    ia = normalize_iata(iata)
    if ia:
        row = session.scalar(select(AirlineMetadata).where(AirlineMetadata.iata_code == ia))
        if row:
            logger.info("[SEMANTIC_MATCH] Matched slug=%s via iata=%s existing_slug=%s", slug, ia, row.slug)
            return row

    ic = normalize_icao(icao)
    if ic:
        row = session.scalar(select(AirlineMetadata).where(AirlineMetadata.icao_code == ic))
        if row:
            logger.info("[SEMANTIC_MATCH] Matched slug=%s via icao=%s existing_slug=%s", slug, ic, row.slug)
            return row

    if name_norm_hint:
        hint = canonical_airline_slug(name_norm_hint)
        if hint:
            row = session.scalar(
                select(AirlineMetadata).where(
                    func.lower(func.coalesce(func.trim(AirlineMetadata.normalized_name), "")) == hint.lower()
                )
            )
            if row:
                logger.info(
                    "[SEMANTIC_MATCH] Matched slug=%s via normalized_name existing_slug=%s",
                    slug,
                    row.slug,
                )
                return row

    return slug_lookup.get(slug)


def merge_airline_metadata_from_openflights(
    existing: AirlineMetadata,
    ofa: OpenFlightsAirline,
    *,
    alliance_id: str | None,
    alliance_code: str | None,
    region: str | None,
    now: datetime,
) -> bool:
    """Non-destructive merge: fills gaps, boosts confidence, merges lineage."""
    updated = False
    if len((ofa.name or "")) > len(existing.airline_name or ""):
        existing.airline_name = ofa.name
        updated = True

    if ofa.iata:
        ni = normalize_iata(ofa.iata)
        if ni and not existing.iata_code:
            existing.iata_code = ni
            updated = True

    if ofa.icao and not existing.icao_code:
        existing.icao_code = normalize_icao(ofa.icao)
        updated = True

    if ofa.callsign and not existing.callsign:
        existing.callsign = ofa.callsign.strip()[:120]
        updated = True

    if ofa.country and not existing.country:
        existing.country = ofa.country
        updated = True
    if ofa.country and not existing.canonical_country:
        existing.canonical_country = ofa.country
        updated = True

    if region and not existing.region:
        existing.region = region
        updated = True

    if alliance_id and not existing.alliance_id:
        existing.alliance_id = alliance_id
        updated = True
    if alliance_code and not existing.alliance_code:
        existing.alliance_code = alliance_code
        updated = True

    canonical_slug = canonical_airline_slug(ofa.name)
    if canonical_slug and (not existing.normalized_name):
        existing.normalized_name = canonical_slug
        updated = True

    patch_raw = {"openflights": {"id": ofa.openflights_id, "alias": ofa.alias}}
    merged = merge_raw_metadata(
        existing.raw_metadata if isinstance(existing.raw_metadata, dict) else {}, patch_raw
    )
    if merged != existing.raw_metadata:
        existing.raw_metadata = merged
        updated = True

    if updated:
        existing.last_enriched_at = now
        existing.last_seen_at = now
        existing.enrichment_status = existing.enrichment_status or "canonical"
        existing.enrichment_confidence = max(float(existing.enrichment_confidence), 0.9)
        existing.source_confidence = max(float(existing.source_confidence), 0.9)
        existing.normalization_confidence = max(float(existing.normalization_confidence), 1.0)
        existing.metadata_quality_score = max(float(existing.metadata_quality_score), 0.8)

    return updated


@dataclass
class IdentityStats:
    slug_collisions_avoided: int = 0
    semantic_matches: int = 0
    upserts: int = 0
    merges: int = 0
    conflict_recoveries: int = 0


def resolve_airline_identity(
    session: Session,
    ofa: OpenFlightsAirline,
    slug_lookup: dict[str, AirlineMetadata],
    *,
    alliance_id: str | None,
    alliance_code: str | None,
    region: str | None,
    now: datetime,
    identity_stats: IdentityStats | None = None,
) -> tuple[AirlineMetadata | None, str, bool]:
    """Resolve OpenFlights row to existing row or NEW placeholder state.

    Returns (entity, action, changed) where action in ("merge", "create", "skip").
    """

    slug = canonical_airline_slug(ofa.name)
    if not slug:
        return None, "skip", False

    existing = slug_lookup.get(slug)
    if not existing:
        existing = semantic_airline_lookup(
            session, slug, ofa.iata, ofa.icao, slug_lookup, name_norm_hint=ofa.name
        )

    if existing:
        if isinstance(identity_stats, IdentityStats) and existing.slug != slug:
            identity_stats.semantic_matches += 1
        slug_lookup.setdefault(slug, existing)
        changed = merge_airline_metadata_from_openflights(
            existing,
            ofa,
            alliance_id=alliance_id,
            alliance_code=alliance_code,
            region=region,
            now=now,
        )
        if isinstance(identity_stats, IdentityStats) and changed:
            identity_stats.merges += 1
        return existing, "merge", changed

    meta = AirlineMetadata(
        airline_name=ofa.name,
        slug=slug,
        iata_code=normalize_iata(ofa.iata),
        icao_code=normalize_icao(ofa.icao),
        callsign=(ofa.callsign or "").strip()[:120] or None,
        country=ofa.country,
        canonical_country=ofa.country,
        region=region,
        normalized_name=slug,
        alliance_id=alliance_id,
        alliance_code=alliance_code,
        airline_type="full_service",
        enrichment_confidence=0.9,
        normalization_confidence=1.0,
        metadata_quality_score=0.8,
        enrichment_status="canonical",
        coverage_status="openflights",
        source_confidence=0.9,
        raw_metadata={"openflights": {"id": ofa.openflights_id, "alias": ofa.alias}},
        last_enriched_at=now,
        last_seen_at=now,
    )
    session.add(meta)
    slug_lookup[slug] = meta
    if isinstance(identity_stats, IdentityStats):
        identity_stats.upserts += 1
    return meta, "create", True


def record_identity_metrics(**kwargs: float) -> None:
    try:
        from app.observability import record_worker_metric

        for k, v in kwargs.items():
            record_worker_metric(k, float(v))
    except Exception:
        pass


def recover_unique_violation_slug(
    session: Session,
    slug: str,
    ofa: OpenFlightsAirline,
    slug_lookup: dict[str, AirlineMetadata],
    *,
    alliance_id: str | None,
    alliance_code: str | None,
    region: str | None,
    now: datetime,
) -> AirlineMetadata | None:
    """Post-IntegrityError: load canonical row and merge (single retry path)."""
    logger.warning("[DUPLICATE_DETECTED] UniqueViolation recovery slug=%s name=%s", slug, ofa.name)
    session.expire_all()
    row = session.scalar(select(AirlineMetadata).where(AirlineMetadata.slug == slug))
    if not row:
        row = semantic_airline_lookup(session, slug, ofa.iata, ofa.icao, slug_lookup)
    if row:
        slug_lookup[slug] = row
        merge_airline_metadata_from_openflights(
            row,
            ofa,
            alliance_id=alliance_id,
            alliance_code=alliance_code,
            region=region,
            now=now,
        )
        record_identity_metrics(skytrax_conflict_recoveries=1.0, skytrax_aviation_merges=1.0)
        return row
    return None


def audit_aviation_identity_health(session: Session) -> dict[str, Any]:
    """Lightweight governance report for health payloads."""
    sql = (
        select(AirlineMetadata.iata_code, func.count(AirlineMetadata.id).label("cnt"))
        .where(AirlineMetadata.iata_code.isnot(None))
        .group_by(AirlineMetadata.iata_code)
        .having(func.count(AirlineMetadata.id) > 1)
    )
    dup_iata_groups = session.execute(sql).fetchall()

    duplicate_iata_codes = sum(int(row[1]) - 1 for row in dup_iata_groups)
    rows_with_iata = (
        session.scalar(
            select(func.count()).select_from(AirlineMetadata).where(AirlineMetadata.iata_code.isnot(None))
        )
        or 0
    )

    return {
        "canonical_identity_consistent": len(dup_iata_groups) == 0,
        "slug_collision_rate": 0.0,
        "semantic_duplicates_detected": len(dup_iata_groups),
        "canonical_identity_duplicate_iata_codes": duplicate_iata_codes,
        "identity_records_with_iata": rows_with_iata,
        "identity_merge_count": None,
    }
