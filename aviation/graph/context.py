"""Graph-ready context builder for aviation entities.

Builds adjacency structures without requiring Neo4j.
Designed to be portable to a graph DB in the future.
"""
from __future__ import annotations

from collections import defaultdict
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

    def hub_adjacency(self) -> dict[str, Any]:
        """Airport-airline adjacency map for hub topology."""
        links = self.session.query(AirlineAirport).all()
        adj: dict[str, list[str]] = defaultdict(list)
        for link in links:
            ap = self.session.query(AirportMetadata).get(link.airport_metadata_id)
            am = self.session.query(AirlineMetadata).get(link.airline_metadata_id)
            if ap and am:
                key = ap.iata or ap.airport_name
                adj[key].append(am.slug)
        return {"adjacency_type": "hub_airline", "nodes": len(adj), "map": dict(adj)}

    def alliance_topology(self) -> dict[str, Any]:
        """Alliance membership graph."""
        alliances = self.session.query(Alliance).all()
        topology = {}
        for alliance in alliances:
            members = self.session.query(AirlineMetadata).filter_by(alliance_id=alliance.id).all()
            topology[alliance.name] = {
                "id": alliance.id,
                "members": [{"slug": m.slug, "name": m.airline_name, "country": m.country} for m in members],
                "countries": list({m.country for m in members if m.country}),
            }
        return {"topology_type": "alliance_membership", "alliances": len(topology), "map": topology}

    def regional_clusters(self) -> dict[str, Any]:
        """Country-based airline clustering."""
        clusters: dict[str, list[str]] = defaultdict(list)
        for am in self.session.query(AirlineMetadata).filter(AirlineMetadata.country.isnot(None)).all():
            clusters[am.country].append(am.slug)
        return {
            "topology_type": "regional_cluster",
            "regions": len(clusters),
            "map": {k: v for k, v in sorted(clusters.items(), key=lambda x: -len(x[1]))},
        }
