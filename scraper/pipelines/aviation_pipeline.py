"""Scrapy pipeline for persisting aviation metadata items."""
from __future__ import annotations

from datetime import datetime, timezone

from itemadapter import ItemAdapter
from sqlalchemy.exc import IntegrityError

from database.models.aviation import AirlineMetadata, AirportMetadata, Alliance
from database.session import SessionLocal
from scraper.items_aviation import AirlineMetadataItem, AirportMetadataItem


class AviationMetadataPipeline:
    def open_spider(self, spider):
        self.session = SessionLocal()
        self.upserted = 0

    def close_spider(self, spider):
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
        self.session.close()
        spider.logger.info("aviation_metadata_pipeline_closed", extra={"upserted": self.upserted})

    def process_item(self, item, spider):
        if isinstance(item, AirlineMetadataItem):
            self._upsert_airline(ItemAdapter(item), spider)
        elif isinstance(item, AirportMetadataItem):
            self._upsert_airport(ItemAdapter(item), spider)
        return item

    def _resolve_alliance(self, alliance_name: str | None) -> str | None:
        if not alliance_name:
            return None
        slug = alliance_name.lower().replace(" ", "-")
        alliance = self.session.query(Alliance).filter_by(slug=slug).first()
        if not alliance:
            alliance = Alliance(name=alliance_name, slug=slug)
            self.session.add(alliance)
            self.session.flush()
        return alliance.id

    def _upsert_airline(self, item: ItemAdapter, spider) -> None:
        slug = item["slug"]
        record = self.session.query(AirlineMetadata).filter_by(slug=slug).first()
        alliance_id = self._resolve_alliance(item.get("alliance"))

        fields = dict(
            airline_name=item["airline_name"],
            country=item.get("country"),
            alliance_id=alliance_id,
            airline_type=item.get("airline_type"),
            star_rating=item.get("star_rating"),
            is_low_cost=item.get("is_low_cost", False),
            is_premium=item.get("is_premium", False),
            hub_airports=item.get("hub_airports", []),
            certifications=item.get("certifications", []),
            operational_labels=item.get("operational_labels", []),
            skytrax_url=item.get("skytrax_url"),
            raw_metadata=item.get("raw_metadata", {}),
            enrichment_confidence=0.7,
            last_enriched_at=datetime.now(timezone.utc),
        )

        if record:
            for k, v in fields.items():
                setattr(record, k, v)
        else:
            record = AirlineMetadata(slug=slug, **fields)
            self.session.add(record)

        self._flush(spider)

    def _upsert_airport(self, item: ItemAdapter, spider) -> None:
        iata = item.get("iata")
        name = item["airport_name"]

        record = None
        if iata:
            record = self.session.query(AirportMetadata).filter_by(iata=iata).first()
        if not record:
            record = self.session.query(AirportMetadata).filter_by(airport_name=name).first()

        fields = dict(
            airport_name=name,
            iata=iata,
            icao=item.get("icao"),
            city=item.get("city"),
            country=item.get("country"),
            region=item.get("region"),
            latitude=item.get("latitude"),
            longitude=item.get("longitude"),
            passenger_volume=item.get("passenger_volume"),
            airport_rating=item.get("airport_rating"),
            hub_level=item.get("hub_level"),
            operational_labels=item.get("operational_labels", []),
            skytrax_url=item.get("skytrax_url"),
            raw_metadata=item.get("raw_metadata", {}),
            enrichment_confidence=0.7,
            last_enriched_at=datetime.now(timezone.utc),
        )

        if record:
            for k, v in fields.items():
                if v is not None:
                    setattr(record, k, v)
        else:
            record = AirportMetadata(**fields)
            self.session.add(record)

        self._flush(spider)

    def _flush(self, spider) -> None:
        try:
            self.session.flush()
            self.upserted += 1
        except IntegrityError:
            self.session.rollback()
