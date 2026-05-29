"""Aviation Knowledge Graph — builds and maintains a graph of aviation entities and relationships.

Node types: airline, airport, alliance, country, route, aircraft, topic
Edge types: operates_from, belongs_to_alliance, flies_to, complaint_about,
            deteriorating_in, hub_of, country_of
"""

from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.core import Airline, Review
from database.models.graph import GraphNode, GraphEdge, ReviewIntelligence

logger = logging.getLogger(__name__)


class AviationKnowledgeGraph:
    """Build and query the aviation knowledge graph from reviews and metadata."""

    def __init__(self, session: Session):
        self.session = session
        self._node_cache: dict[tuple[str, str], str] = {}

    def ensure_node(self, node_type: str, entity_id: str, label: str, properties: dict | None = None) -> str:
        cache_key = (node_type, entity_id)
        if cache_key in self._node_cache:
            return self._node_cache[cache_key]

        node = self.session.query(GraphNode).filter_by(node_type=node_type, entity_id=entity_id).first()
        if node:
            node.mention_count += 1
            if properties:
                merged = {**(node.properties or {}), **properties}
                node.properties = merged
            self._node_cache[cache_key] = node.id
            return node.id

        node = GraphNode(
            node_type=node_type,
            entity_id=entity_id,
            label=label,
            properties=properties or {},
            mention_count=1,
        )
        self.session.add(node)
        self.session.flush()
        self._node_cache[cache_key] = node.id
        return node.id

    def ensure_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        weight: float = 1.0,
        properties: dict | None = None,
    ) -> str:
        edge = (
            self.session.query(GraphEdge)
            .filter_by(source_node_id=source_id, target_node_id=target_id, edge_type=edge_type)
            .first()
        )
        if edge:
            edge.weight += weight
            if properties:
                merged = {**(edge.properties or {}), **properties}
                edge.properties = merged
            return edge.id

        edge = GraphEdge(
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=edge_type,
            weight=weight,
            properties=properties or {},
        )
        self.session.add(edge)
        self.session.flush()
        return edge.id

    def update_from_corpus(self) -> dict:
        """Build graph from airlines, reviews, and extracted intelligence."""
        nodes_created = edges_created = 0

        airlines = self.session.query(Airline).filter(Airline.is_active.is_(True)).all()
        for airline in airlines:
            a_nid = self.ensure_node(
                "airline",
                airline.slug,
                airline.name,
                {
                    "country": airline.country,
                    "source": airline.source,
                },
            )
            nodes_created += 1

            if airline.country:
                c_nid = self.ensure_node("country", airline.country.lower(), airline.country)
                self.ensure_edge(a_nid, c_nid, "country_of")
                edges_created += 1

        try:
            from database.models.aviation import AirlineMetadata, AirportMetadata, Alliance

            alliances = self.session.query(Alliance).all()
            for alliance in alliances:
                al_nid = self.ensure_node("alliance", alliance.slug, alliance.name)
                nodes_created += 1

            airline_metas = self.session.query(AirlineMetadata).all()
            for am in airline_metas:
                a_nid = self.ensure_node("airline", am.slug, am.name)
                if am.alliance_id:
                    alliance = self.session.query(Alliance).get(am.alliance_id)
                    if alliance:
                        al_nid = self.ensure_node("alliance", alliance.slug, alliance.name)
                        self.ensure_edge(a_nid, al_nid, "belongs_to_alliance")
                        edges_created += 1
                for hub in am.hub_airports or []:
                    h_nid = self.ensure_node("airport", hub.upper(), hub.upper())
                    self.ensure_edge(a_nid, h_nid, "hub_of")
                    edges_created += 1
                    nodes_created += 1

            airports = self.session.query(AirportMetadata).all()
            for ap in airports:
                iata = ap.iata or ap.airport_name
                ap_nid = self.ensure_node(
                    "airport",
                    iata,
                    ap.airport_name,
                    {
                        "city": ap.city,
                        "country": ap.country,
                        "region": ap.region,
                        "rating": ap.airport_rating,
                        "hub_level": ap.hub_level,
                    },
                )
                nodes_created += 1
                if ap.country:
                    c_nid = self.ensure_node("country", ap.country.lower(), ap.country)
                    self.ensure_edge(ap_nid, c_nid, "country_of")
                    edges_created += 1
        except Exception as exc:
            logger.warning("[OPS][GRAPH] Aviation metadata import partial: %s", exc)

        intels = (
            self.session.query(ReviewIntelligence, Review)
            .join(Review, Review.id == ReviewIntelligence.review_id)
            .all()
        )
        for ri, review in intels:
            airline = self.session.query(Airline).get(review.airline_id)
            if not airline:
                continue
            a_nid = self.ensure_node("airline", airline.slug, airline.name)

            for code in ri.airport_mentions:
                ap_nid = self.ensure_node("airport", code, code)
                self.ensure_edge(a_nid, ap_nid, "operates_from", weight=0.5)
                edges_created += 1
                nodes_created += 1

            for aircraft in ri.aircraft_mentions:
                ac_nid = self.ensure_node("aircraft", aircraft.lower().replace(" ", "-"), aircraft)
                self.ensure_edge(a_nid, ac_nid, "flies_with")
                edges_created += 1
                nodes_created += 1

            for route in ri.route_mentions:
                if route.get("origin") and route.get("destination"):
                    route_id = f"{route['origin']}-{route['destination']}"
                    r_nid = self.ensure_node("route", route_id, route_id)
                    self.ensure_edge(a_nid, r_nid, "flies_route")
                    edges_created += 1
                    nodes_created += 1

            for k, v in ri.disruptions.items():
                if v:
                    self.ensure_edge(
                        a_nid, self.ensure_node("topic", k, k.replace("_", " ").title()), "complaint_about"
                    )
                    edges_created += 1

        self.session.commit()

        stats = self.get_stats()
        logger.info(
            "[OPS][GRAPH] Updated: nodes=%d edges=%d (delta: +%d nodes, +%d edges)",
            stats["total_nodes"],
            stats["total_edges"],
            nodes_created,
            edges_created,
        )
        return {**stats, "nodes_created": nodes_created, "edges_created": edges_created}

    def get_stats(self) -> dict:
        total_nodes = self.session.query(func.count(GraphNode.id)).scalar() or 0
        total_edges = self.session.query(func.count(GraphEdge.id)).scalar() or 0
        type_counts = dict(
            self.session.query(GraphNode.node_type, func.count(GraphNode.id))
            .group_by(GraphNode.node_type)
            .all()
        )
        edge_type_counts = dict(
            self.session.query(GraphEdge.edge_type, func.count(GraphEdge.id))
            .group_by(GraphEdge.edge_type)
            .all()
        )
        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "node_types": type_counts,
            "edge_types": edge_type_counts,
        }
