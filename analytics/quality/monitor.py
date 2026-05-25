from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models import DataQualityReport, Review


class DataQualityMonitor:
    """Detect invalid reviews, spikes, duplicates and suspicious ratings."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def run_scan(self) -> dict:
        findings: list[dict] = []
        sample_size = int(self.session.query(func.count(Review.id)).scalar() or 0)

        missing_fields = (
            self.session.query(func.count(Review.id))
            .filter((Review.text.is_(None)) | (Review.text == "") | Review.rating.is_(None))
            .scalar()
            or 0
        )
        if missing_fields:
            findings.append(
                {
                    "check": "missing_fields",
                    "count": int(missing_fields),
                    "detail": "Reviews with empty text or missing rating detected.",
                }
            )

        duplicate_fps = (
            self.session.query(Review.fingerprint, func.count(Review.id))
            .group_by(Review.fingerprint)
            .having(func.count(Review.id) > 1)
            .all()
        )
        if duplicate_fps:
            findings.append(
                {
                    "check": "duplicate_fingerprints",
                    "count": len(duplicate_fps),
                    "detail": "Duplicate fingerprint groups found (should be prevented by constraint).",
                }
            )

        suspicious = (
            self.session.query(func.count(Review.id))
            .filter((Review.rating < 0) | (Review.rating > 10))
            .scalar()
            or 0
        )
        if suspicious:
            findings.append(
                {
                    "check": "suspicious_ratings",
                    "count": int(suspicious),
                    "detail": "Ratings outside expected 0-10 range.",
                }
            )

        since = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = (
            self.session.query(func.count(Review.id)).filter(Review.created_at >= since).scalar() or 0
        )
        baseline = max((sample_size - recent) / 30, 1)
        if recent > baseline * 5:
            findings.append(
                {
                    "check": "ingestion_spike",
                    "count": int(recent),
                    "detail": f"24h ingestion spike: {recent} reviews vs daily baseline ~{round(baseline)}.",
                }
            )

        invalid_text = (
            self.session.query(func.count(Review.id))
            .filter(func.length(Review.text) < 20)
            .scalar()
            or 0
        )
        if invalid_text:
            findings.append(
                {
                    "check": "invalid_reviews",
                    "count": int(invalid_text),
                    "detail": "Very short review text detected.",
                }
            )

        severity = "low"
        if any(item["check"] in {"duplicate_fingerprints", "suspicious_ratings", "ingestion_spike"} for item in findings):
            severity = "high"
        elif findings:
            severity = "medium"

        report = DataQualityReport(
            report_type="full_scan",
            severity=severity,
            findings=findings,
            sample_size=sample_size,
        )
        self.session.add(report)
        self.session.commit()
        return {"severity": severity, "findings_count": len(findings), "sample_size": sample_size}

    def list_reports(self, limit: int = 20) -> list[dict]:
        rows = self.session.query(DataQualityReport).order_by(DataQualityReport.generated_at.desc()).limit(limit).all()
        return [
            {
                "id": row.id,
                "report_type": row.report_type,
                "severity": row.severity,
                "findings": row.findings,
                "sample_size": row.sample_size,
                "generated_at": row.generated_at.isoformat(),
            }
            for row in rows
        ]
