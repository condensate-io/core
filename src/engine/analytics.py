import uuid
import networkx as nx
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.db.models import Relation, Entity, Assertion
from typing import Dict, List, Any

class GraphAnalyst:
    def __init__(self, db: Session, project_id: uuid.UUID):
        self.db = db
        self.project_id = project_id
        self.graph = self._build_graph()

    def _build_graph(self) -> nx.DiGraph:
        """
        Construct a directed graph from the project's entities and relations.
        """
        G = nx.DiGraph()
        
        # Load Entities as nodes
        entities = self.db.execute(
            select(Entity).where(Entity.project_id == self.project_id)
        ).scalars().all()
        for e in entities:
            G.add_node(str(e.id), label=e.canonical_name, type=e.type)
            
        # Load Relations as edges
        relations = self.db.execute(
            select(Relation).where(Relation.project_id == self.project_id)
        ).scalars().all()
        for r in relations:
            G.add_edge(str(r.from_id), str(r.to_id), type=r.relation_type, weight=r.strength)
            
        return G

    def get_centrality(self) -> List[Dict[str, Any]]:
        """
        Calculate PageRank centrality for entities to identify key actors/concepts.
        """
        if not self.graph.nodes:
            return []
        try:
            # Use pagerank for directed importance
            pagerank = nx.pagerank(self.graph, weight='weight')
            sorted_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
            
            results = []
            for node_id, score in sorted_nodes:
                node_data = self.graph.nodes.get(node_id, {})
                results.append({
                    "id": node_id,
                    "label": node_data.get("label", "Unknown"),
                    "score": round(score, 4)
                })
            return results
        except Exception:
            return []

    def get_communities(self) -> List[Dict[str, Any]]:
        """
        Detect tightly coupled clusters (communities) in the simulation graph.
        """
        if not self.graph.nodes:
            return []
        try:
            # Convert to undirected for community detection
            undirected = self.graph.to_undirected()
            communities = list(nx.community.label_propagation_communities(undirected))
            
            results = []
            for i, comm in enumerate(communities):
                results.append({
                    "community_id": i,
                    "nodes": [self.graph.nodes.get(n, {}).get("label", n) for n in comm]
                })
            return results
        except Exception:
            return []

    def get_bottlenecks(self) -> List[Dict[str, Any]]:
        """
        Identify entities with high betweenness centrality (potential single points of failure).
        """
        if not self.graph.nodes:
            return []
        try:
            betweenness = nx.betweenness_centrality(self.graph, weight='weight')
            sorted_nodes = sorted(betweenness.items(), key=lambda x: x[1], reverse=True)
            
            results = []
            for node_id, score in sorted_nodes[:15]: # Top 15 bottlenecks
                node_data = self.graph.nodes.get(node_id, {})
                results.append({
                    "id": node_id,
                    "label": node_data.get("label", "Unknown"),
                    "score": round(score, 4)
                })
            return results
        except Exception:
            return []
