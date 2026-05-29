"""Aviation Master Data Sync — persist canonical data from external sources.

This service:
1. Downloads OpenFlights airlines + airports
2. Downloads OurAirports for enhanced coordinate/municipality data
3. Resolves alliances deterministically
4. Persists enriched records into AirlineMetadata / AirportMetadata
5. Links airline_metadata to core Airline via slug matching
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from aviation.master_data.alliances import (
    ALLIANCES,
    resolve_alliance_by_iata,
    resolve_alliance_by_name,
)
from aviation.master_data.normalize import normalize_airline_slug, resolve_region
from aviation.master_data.sources import (
    OpenFlightsAirline,
    OpenFlightsAirport,
    OurAirportsRecord,
    fetch_openflights_airlines,
    fetch_openflights_airports,
    fetch_ourairports,
)
from database.models.aviation import AirlineMetadata, AirportMetadata, Alliance
from database.models.core import Airline

logger = logging.getLogger(__name__)


class AviationMasterSync:
    """Orchestrates canonical aviation data synchronization."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.stats = {
            "airlines_created": 0,
            "airlines_updated": 0,
            "airlines_skipped": 0,
            "airports_created": 0,
            "airports_updated": 0,
            "alliances_synced": 0,
            "links_created": 0,
        }

    def run(self) -> dict:
        """Execute full master data sync."""
        logger.info("[AVIATION_MASTER] Starting full sync...")

        try:
            from database.runtime_schema import ensure_aviation_runtime_ready
            from database.session import engine

            runtime = ensure_aviation_runtime_ready(engine)
            if not runtime.get("iata_code_ready"):
                msg = (
                    "airline_metadata schema drift: missing columns "
                    f"{runtime.get('missing_physical_columns', ['iata_code'])}"
                )
                logger.error("[AVIATION_MASTER] %s", msg)
                return {
                    "error": msg,
                    "schema_drift": True,
                    "runtime_schema": runtime,
                    **self.stats,
                }
        except Exception as exc:
            logger.warning("[AVIATION_MASTER] Schema preflight skipped: %s", exc)

        self._ensure_alliances()

        of_airlines = fetch_openflights_airlines()
        of_airports = fetch_openflights_airports()

        try:
            oa_airports = fetch_ourairports()
        except Exception as e:
            logger.warning("[AVIATION_MASTER] OurAirports fetch failed: %s", e)
            oa_airports = []

        self._sync_airlines(of_airlines)
        self._sync_airports(of_airports, oa_airports)
        self._link_to_core_airlines()
        self._backfill_from_core()

        self.session.commit()
        self._attach_aviation_totals()
        logger.info("[AVIATION_MASTER] Sync complete: %s", self.stats)
        return self.stats

    def _attach_aviation_totals(self) -> None:
        """Accumulated aviation KPIs (distinct from per-run created/updated deltas)."""
        from sqlalchemy import func

        total = self.session.query(func.count(AirlineMetadata.id)).scalar() or 0
        linked = (
            self.session.query(func.count(AirlineMetadata.id))
            .filter(AirlineMetadata.airline_id.isnot(None))
            .scalar()
            or 0
        )
        self.stats["airlines_total"] = int(total)
        self.stats["airlines_linked_total"] = int(linked)
        self.stats["airlines_processed_this_run"] = int(
            self.stats.get("airlines_created", 0) + self.stats.get("airlines_updated", 0)
        )

    def _ensure_alliances(self) -> None:
        """Seed the three major alliances."""
        for name, info in ALLIANCES.items():
            existing = self.session.query(Alliance).filter_by(slug=info["slug"]).first()
            if not existing:
                self.session.add(
                    Alliance(
                        name=name,
                        slug=info["slug"],
                        founded_year=info.get("founded_year"),
                        headquarters=info.get("headquarters"),
                    )
                )
                self.stats["alliances_synced"] += 1
        self.session.flush()

    def _resolve_alliance_id(self, iata: str | None, name: str) -> str | None:
        """Deterministically resolve alliance_id for an airline."""
        alliance_name = resolve_alliance_by_iata(iata)
        if not alliance_name:
            alliance_name = resolve_alliance_by_name(name)
        if not alliance_name:
            return None

        slug = ALLIANCES[alliance_name]["slug"]
        alliance = self.session.query(Alliance).filter_by(slug=slug).first()
        return alliance.id if alliance else None

    def _sync_airlines(self, of_airlines: list[OpenFlightsAirline], *, _recovery_flush: bool = False) -> None:
        """Persist OpenFlights airlines with MDM identity resolution (slug-safe).

        SessionLocal uses autoflush=False — always resolve via slug_lookup + merges to avoid
        duplicate INSERTs hitting airline_metadata.slug unique constraint.
        """
        from aviation.aviation_identity_governance import (
            IdentityStats,
            build_airline_slug_lookup,
            canonical_airline_slug,
            record_identity_metrics,
            resolve_airline_identity,
        )

        now = datetime.now(timezone.utc)
        slug_lookup = build_airline_slug_lookup(self.session)
        identity_stats = IdentityStats()
        of_slug_stream: set[str] = set()
        created_local = updated_local = skipped_local = 0

        try:
            with self.session.begin_nested():
                for ofa in of_airlines:
                    if not ofa.name or not ofa.active:
                        skipped_local += 1
                        continue

                    slug = canonical_airline_slug(ofa.name)
                    if not slug:
                        skipped_local += 1
                        continue

                    if slug in of_slug_stream:
                        identity_stats.slug_collisions_avoided += 1
                    of_slug_stream.add(slug)

                    alliance_id = self._resolve_alliance_id(ofa.iata, ofa.name)
                    region = resolve_region(ofa.country)
                    alliance_code = resolve_alliance_by_iata(ofa.iata) or resolve_alliance_by_name(ofa.name)

                    _entity, action, changed = resolve_airline_identity(
                        self.session,
                        ofa,
                        slug_lookup,
                        alliance_id=alliance_id,
                        alliance_code=alliance_code,
                        region=region,
                        now=now,
                        identity_stats=identity_stats,
                    )
                    if action == "skip":
                        skipped_local += 1
                        continue
                    if action == "merge" and changed:
                        updated_local += 1
                    elif action == "create":
                        created_local += 1

                self.session.flush()
        except IntegrityError as exc:
            err = str(exc).lower()
            if not _recovery_flush and ("slug" in err or "airline_metadata_slug" in err):
                logger.warning(
                    "[AVIATION_MASTER][DUPLICATE_DETECTED] airline slug flush conflict — nested rollback "
                    "and rebuild lookup (recovery flush)"
                )
                record_identity_metrics(skytrax_conflict_recoveries=1.0)
                self._sync_airlines(of_airlines, _recovery_flush=True)
                return
            raise

        self.stats["airlines_created"] += created_local
        self.stats["airlines_updated"] += updated_local
        self.stats["airlines_skipped"] += skipped_local

        logger.info(
            "[AVIATION_MASTER][AVIATION_IDENTITY] slug_collisions_avoided=%d semantic_matches=%d "
            "merges=%d upserts=%d op=sync",
            identity_stats.slug_collisions_avoided,
            identity_stats.semantic_matches,
            identity_stats.merges,
            identity_stats.upserts,
        )
        record_identity_metrics(
            skytrax_aviation_slug_collisions=float(identity_stats.slug_collisions_avoided),
            skytrax_semantic_duplicate_matches=float(identity_stats.semantic_matches),
            skytrax_aviation_merges=float(identity_stats.merges),
            skytrax_aviation_upserts=float(identity_stats.upserts),
            skytrax_identity_resolution_success=1.0,
        )

        logger.info(
            "[AVIATION_MASTER] Airlines: %d created, %d updated, %d skipped",
            self.stats["airlines_created"],
            self.stats["airlines_updated"],
            self.stats["airlines_skipped"],
        )

    def _sync_airports(
        self,
        of_airports: list[OpenFlightsAirport],
        oa_airports: list[OurAirportsRecord],
    ) -> None:
        """Persist airports from OpenFlights, enhanced with OurAirports data."""
        now = datetime.now(timezone.utc)

        oa_by_iata: dict[str, OurAirportsRecord] = {}
        for oa in oa_airports:
            if oa.iata_code:
                oa_by_iata[oa.iata_code.upper()] = oa

        for ofap in of_airports:
            if not ofap.iata:
                continue

            iata = ofap.iata.upper()
            existing = self.session.query(AirportMetadata).filter_by(iata=iata).first()

            oa_record = oa_by_iata.get(iata)
            city = ofap.city
            municipality = oa_record.municipality if oa_record else None
            region = None
            if ofap.country:
                region = resolve_region(ofap.country)

            if existing:
                updated = False
                if ofap.icao and not existing.icao:
                    existing.icao = ofap.icao
                    updated = True
                if ofap.country and not existing.country:
                    existing.country = ofap.country
                    updated = True
                if region and not existing.region:
                    existing.region = region
                    updated = True
                if ofap.latitude and not existing.latitude:
                    existing.latitude = ofap.latitude
                    existing.longitude = ofap.longitude
                    updated = True
                if municipality and not existing.city:
                    existing.city = municipality
                    updated = True
                if updated:
                    existing.last_enriched_at = now
                    existing.enrichment_status = "canonical"
                    self.stats["airports_updated"] += 1
            else:
                self.session.add(
                    AirportMetadata(
                        airport_name=ofap.name,
                        iata=iata,
                        icao=ofap.icao,
                        city=municipality or city,
                        country=ofap.country,
                        region=region,
                        latitude=ofap.latitude,
                        longitude=ofap.longitude,
                        enrichment_confidence=0.9,
                        normalization_confidence=1.0,
                        metadata_quality_score=0.8,
                        enrichment_status="canonical",
                        coverage_status="openflights",
                        source_confidence=0.9,
                        last_enriched_at=now,
                        last_seen_at=now,
                    )
                )
                self.stats["airports_created"] += 1

        self.session.flush()
        logger.info(
            "[AVIATION_MASTER] Airports: %d created, %d updated",
            self.stats["airports_created"],
            self.stats["airports_updated"],
        )

    def _link_to_core_airlines(self) -> None:
        """Link AirlineMetadata to core Airline using multi-strategy matching.

        Strategies (in priority order):
        1. Exact slug match
        2. Normalized name match (re-slug the core airline name)
        3. Substring containment (deterministic, not fuzzy)
        """
        unlinked = self.session.query(AirlineMetadata).filter(AirlineMetadata.airline_id.is_(None)).all()
        core_airlines = self.session.query(Airline).all()
        core_by_slug = {a.slug: a for a in core_airlines}
        core_by_norm = {}
        for a in core_airlines:
            norm = normalize_airline_slug(a.name)
            if norm and norm not in core_by_norm:
                core_by_norm[norm] = a

        linked = 0
        link_methods = {"slug": 0, "normalized": 0, "substring": 0}

        for meta in unlinked:
            match = core_by_slug.get(meta.slug)
            method = "slug"

            if not match:
                norm = normalize_airline_slug(meta.airline_name)
                match = core_by_norm.get(norm)
                method = "normalized"

            if not match:
                meta_lower = meta.airline_name.lower().strip()
                for ca in core_airlines:
                    core_lower = ca.name.lower().strip()
                    if (meta_lower in core_lower or core_lower in meta_lower) and len(
                        min(meta_lower, core_lower, key=len)
                    ) >= 5:
                        match = ca
                        method = "substring"
                        break

            if match:
                meta.airline_id = match.id
                if not meta.country and match.country:
                    meta.country = match.country
                linked += 1
                link_methods[method] += 1

        self.stats["links_created"] = linked
        self.stats["link_methods"] = link_methods
        self.session.flush()
        logger.info(
            "[AVIATION_MASTER] Linked %d metadata records to core airlines (slug=%d, normalized=%d, substring=%d)",
            linked,
            link_methods["slug"],
            link_methods["normalized"],
            link_methods["substring"],
        )

    def _backfill_from_core(self) -> None:
        """Create AirlineMetadata for core airlines that have no metadata record.

        Uses identity slug lookup + semantic resolution to prevent airline_metadata.slug collisions.
        """
        from datetime import datetime, timezone as tz

        from aviation.aviation_identity_governance import (
            build_airline_slug_lookup,
            semantic_airline_lookup,
        )

        slug_lookup = build_airline_slug_lookup(self.session)

        linked_ids = {
            row[0]
            for row in self.session.query(AirlineMetadata.airline_id)
            .filter(AirlineMetadata.airline_id.isnot(None))
            .all()
        }
        core_airlines = self.session.query(Airline).filter(Airline.is_active.is_(True)).all()

        now = datetime.now(tz.utc)
        created = 0
        for ca in core_airlines:
            if ca.id in linked_ids:
                continue
            norm_slug = normalize_airline_slug(ca.name)
            existing = slug_lookup.get(ca.slug) or (slug_lookup.get(norm_slug) if norm_slug else None)
            if not existing:
                existing = semantic_airline_lookup(
                    self.session,
                    norm_slug or ca.slug or "",
                    None,
                    None,
                    slug_lookup,
                    name_norm_hint=ca.name,
                )

            if existing:
                if not existing.airline_id:
                    existing.airline_id = ca.id
                if not existing.country and ca.country:
                    existing.country = ca.country
                slug_lookup.setdefault(ca.slug, existing)
                if norm_slug:
                    slug_lookup.setdefault(norm_slug, existing)
                continue

            alliance_id = self._resolve_alliance_id(None, ca.name)
            region = resolve_region(ca.country) if ca.country else None

            new_meta = AirlineMetadata(
                airline_id=ca.id,
                airline_name=ca.name,
                slug=ca.slug,
                country=ca.country,
                canonical_country=ca.country,
                region=region,
                alliance_id=alliance_id,
                alliance_code=resolve_alliance_by_name(ca.name),
                normalized_name=norm_slug or ca.slug,
                airline_type="full_service",
                enrichment_confidence=0.5,
                normalization_confidence=0.7,
                metadata_quality_score=0.4,
                enrichment_status="backfilled",
                coverage_status="core_only",
                source_confidence=0.6,
                last_enriched_at=now,
                last_seen_at=now,
            )
            self.session.add(new_meta)
            slug_lookup[ca.slug] = new_meta
            if norm_slug:
                slug_lookup[norm_slug] = new_meta
            created += 1

        self.stats["backfilled"] = created
        self.session.flush()
        logger.info("[AVIATION_MASTER] Backfilled %d core airlines into airline_metadata", created)
