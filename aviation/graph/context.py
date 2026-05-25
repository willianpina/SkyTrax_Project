"""Graph-ready context builder for aviation entities.

Builds adjacency structures without requiring Neo4j.
Designed to be portable to a graph DB in the future.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from database.models.aviation import AirlineMetadata, AirportMetadata, AirlineAirport, Alliance


class AviationGraphContext:
    """Build graph-ready context for an airline or airport."""

    def __init__(self, session: Session):
        self.session = session

    def airline_context(self, slug: str) -> dict[str, Any]:
        am = self.session.query(AirlineMetadata).filter_by(slug=slug).first()
        if not am:
            return {"entity": slug, "type": "airline", "edges": []}

        edges = []

        if am.alliance_rel:
            edges.append({
                "target": am.alliance_rel.name,
                "target_type": "alliance",
                "relationship": "member_of",
            })
            siblings = self.session.query(AirlineMetadata).filter(
                AirlineMetadata.alliance_id == am.alliance_id,
                AirlineMetadata.id != am.id,
            ).limit(10).all()
            for sib in siblings:
                edges.append({
                    "target": sib.airline_name,
                    "target_slug": sib.slug,
                    "target_type": "airline",
                    "relationship": "alliance_peer",
                })

        hub_links = self.session.query(AirlineAirport).filter_by(airline_metadata_id=am.id).all()
        for link in hub_links:
            ap = self.session.query(AirportMetadata).get(link.airport_metadata_id)
            if ap:
                edges.append({
                    "target": ap.airport_name,
                    "target_iata": ap.iata,
                    "target_type": "airport",
                    "relationship": link.relationship_type or "hub",
                })

        if am.country:
            edges.append({
                "target": am.country,
                "target_type": "country",
                "relationship": "headquartered_in",
            })

        for label in am.operational_labels:
            edges.append({
                "target": label,
                "target_type": "label",
                "relationship": "tagged_as",
            })

        return {
            "entity": am.airline_name,
            "entity_slug": am.slug,
            "type": "airline",
            "star_rating": am.star_rating,
            "airline_type": am.airline_type,
            "edges": edges,
        }

    def airport_context(self, iata: str) -> dict[str, Any]:
        ap = self.session.query(AirportMetadata).filter_by(iata=iata.upper()).first()
        if not ap:
            return {"entity": iata, "type": "airport", "edges": []}

        edges = []

        links = self.session.query(AirlineAirport).filter_by(airport_metadata_id=ap.id).all()
        for link in links:
            am = self.session.query(AirlineMetadata).get(link.airline_metadata_id)
            if am:
                edges.append({
                    "target": am.airline_name,
                    "target_slug": am.slug,
                    "target_type": "airline",
                    "relationship": link.relationship_type or "hub",
                })

        if ap.country:
            edges.append({"target": ap.country, "target_type": "country", "relationship": "located_in"})
        if ap.region:
            edges.append({"target": ap.region, "target_type": "region", "relationship": "in_region"})

        return {
            "entity": ap.airport_name,
            "entity_iata": ap.iata,
            "type": "airport",
            "hub_level": ap.hub_level,
            "airport_rating": ap.airport_rating,
            "edges": edges,
        }
