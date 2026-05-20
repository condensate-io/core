import uuid
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from src.synapses.models import Synapse, ConsolidatedMemory
from src.synapses.config import synapse_config
from src.db.models import Assertion

class MemoryConsolidator:
    def __init__(self, db: Session):
        self.db = db

    async def run_consolidation_cycle(self, project_id: uuid.UUID):
        """
        Detect dense clusters of synapses and consolidate them into higher-order memories.
        """
        if not synapse_config.ENABLED:
            return

        # 1. Detect clusters (Simplified: nodes with many high-weight synapses)
        # In a real implementation, we'd use a graph clustering algorithm (e.g. Louvain)
        clusters = self.detect_clusters(project_id)
        
        unique_clusters = []
        seen_clusters = set()
        for cluster in clusters:
            cluster_key = tuple(sorted(cluster))
            if cluster_key not in seen_clusters:
                seen_clusters.add(cluster_key)
                unique_clusters.append(cluster)

        for cluster in unique_clusters:
            await self.consolidate_cluster(project_id, cluster)

    def detect_clusters(self, project_id: uuid.UUID) -> List[List[uuid.UUID]]:
        """
        Identify groups of memories using the Louvain community detection algorithm.
        Tries multiple import strategies for different networkx versions.
        """
        import networkx as nx
        import logging
        
        logger = logging.getLogger("Consolidation")
        communities = None

        # Try import strategies in order of preference
        try:
            # Strategy 1: networkx 2.x with community module
            from networkx.community import louvain_communities
            use_louvain = True
            logger.debug("Using networkx.community.louvain_communities")
        except ImportError:
            try:
                # Strategy 2: python-louvain package (networkx 3.x compatibility)
                import community.community_louvain as community_louvain
                def louvain_communities(G, weight=None, seed=None):
                    """Wrapper to match networkx API"""
                    partition = community_louvain.best_partition(G, weight=weight, random_state=seed)
                    # Convert partition dict to list of sets
                    clusters = {}
                    for node, comm_id in partition.items():
                        if comm_id not in clusters:
                            clusters[comm_id] = set()
                        clusters[comm_id].add(node)
                    return list(clusters.values())
                use_louvain = True
                logger.debug("Using community.community_louvain (python-louvain package)")
            except ImportError:
                use_louvain = False
                logger.warning("No Louvain implementation found. Falling back to greedy clustering.")

        # 1. Fetch strong synapses
        stmt = select(Synapse).where(
            (Synapse.project_id == project_id) & 
            (Synapse.weight >= synapse_config.CONSOLIDATION_THRESHOLD)
        )
        strong_synapses = self.db.execute(stmt).scalars().all()
        
        if not strong_synapses:
            logger.info(f"No synapses above threshold {synapse_config.CONSOLIDATION_THRESHOLD} for project {project_id}")
            return []

        # 2. Build Weighted Graph
        G = nx.Graph()
        for s in strong_synapses:
            G.add_edge(s.from_memory_id, s.to_memory_id, weight=s.weight)
            
        if G.number_of_nodes() < 3:
            return []

        # 3. Apply Community Detection Algorithm
        clusters = []
        try:
            if use_louvain:
                # Use Louvain algorithm
                communities = louvain_communities(G, weight='weight', seed=42)
                clusters = [list(c) for c in communities if len(c) >= 3]
            else:
                # Fallback: Greedy clustering based on edge density
                clusters = self._greedy_clustering(G)
            
            if clusters:
                logger.info(f"Detected {len(clusters)} clusters for consolidation in project {project_id}")
            return clusters
        except Exception as e:
            logger.error(f"Community detection failed: {e}. Attempting greedy fallback.")
            try:
                clusters = self._greedy_clustering(G)
                return clusters
            except Exception as fallback_e:
                logger.error(f"Greedy clustering also failed: {fallback_e}")
                return []

    def _greedy_clustering(self, G: Any) -> List[List[uuid.UUID]]:
        """
        Simple greedy clustering algorithm for when Louvain is unavailable.
        Groups nodes with many mutual high-weight connections.
        """
        import logging
        logger = logging.getLogger("Consolidation")
        
        visited = set()
        clusters = []
        
        # Sort nodes by degree (connectivity)
        nodes_by_degree = sorted(G.degree(), key=lambda x: x[1], reverse=True)
        
        for node, _ in nodes_by_degree:
            if node in visited:
                continue
            
            # Start a new cluster with this node
            cluster = {node}
            visited.add(node)
            
            # Add neighbors with high edge weights
            for neighbor in G.neighbors(node):
                if neighbor not in visited:
                    edge_weight = G[node][neighbor].get('weight', 1.0)
                    if edge_weight >= synapse_config.CONSOLIDATION_THRESHOLD * 0.8:  # 80% of threshold
                        cluster.add(neighbor)
                        visited.add(neighbor)
            
            if len(cluster) >= 3:  # Minimum cluster size
                clusters.append(list(cluster))
        
        logger.debug(f"Greedy clustering identified {len(clusters)} clusters")
        return clusters

    async def consolidate_cluster(self, project_id: uuid.UUID, memory_ids: List[uuid.UUID]):
        """
        Synthesize a higher-order memory from a cluster of related memories using LLM.
        """
        from src.llm.client import LLMClient
        from sqlalchemy import select
        llm = LLMClient()

        # Check if this cluster has already been consolidated
        existing_consolidations = self.db.query(ConsolidatedMemory).filter(
            ConsolidatedMemory.project_id == project_id
        ).all()
        
        memory_ids_set = set(memory_ids)
        for existing in existing_consolidations:
            existing_ids_set = set(existing.evidence_ids)
            # If there's significant overlap (e.g., 80% of the smaller set), consider it already consolidated
            overlap = len(memory_ids_set & existing_ids_set)
            min_size = min(len(memory_ids_set), len(existing_ids_set))
            if min_size > 0 and (overlap / min_size) >= 0.8:
                import logging
                logging.getLogger("Consolidation").info(
                    f"Cluster already consolidated for project {project_id} (overlap: {overlap}/{min_size}), skipping"
                )
                return

        # 1. Fetch memory content and metadata
        stmt = select(Assertion).where(Assertion.id.in_(memory_ids))
        assertions = self.db.execute(stmt).scalars().all()
        
        if not assertions:
            return

        # 2. Format context for LLM
        cluster_context = "\n".join([
            f"- Memory [{a.id}]: {a.subject_text} {a.predicate} {a.object_text} (confidence: {a.confidence})" 
            for a in assertions
        ])
        
        prompt = f"""
I have identified a dense cluster of related memories in our knowledge graph. 
Your task is to synthesize these related facts into a single, high-fidelity "Higher-Order Learning" or "Policy".

### Related Memories:
{cluster_context}

### Instructions:
1. Identify the core underlying pattern, preference, or rule that connects these memories.
2. Formulate a clear, concise statement that captures this higher-order insight.
3. If the memories describe a pattern of behavior, frame it as a "Learning".
4. If the memories describe a constraint or requirement, frame it as a "Policy".
5. Output ONLY the synthesized statement.

Synthesized Statement:
"""
        
        try:
            # 3. Generate high-fidelity synthesis
            synthesized_content = await llm.generate(
                prompt=prompt,
                system_prompt="You are a Meta-Cognitive Engine. Your goal is to synthesize low-level memories into higher-order patterns."
            )
            
            # Clean up synthesis (Ollama sometimes adds extra text or markdown)
            synthesized_content = synthesized_content.strip().strip('"').strip("'")
            
            # Avoid duplicate consolidated memories with identical content
            existing_content_stmt = select(ConsolidatedMemory).where(
                (ConsolidatedMemory.project_id == project_id) &
                (ConsolidatedMemory.content == synthesized_content)
            )
            if self.db.execute(existing_content_stmt).scalars().first():
                import logging
                logging.getLogger("Consolidation").info(
                    f"Duplicate consolidated memory content already exists for project {project_id}, skipping"
                )
                return

            # 4. Save consolidated memory
            cm = ConsolidatedMemory(
                project_id=project_id,
                content=synthesized_content,
                evidence_ids=memory_ids,
                confidence=sum(a.confidence for a in assertions) / len(assertions) # Avg confidence
            )
            self.db.add(cm)
            self.db.commit()
            
            import logging
            logging.getLogger("Consolidation").info(f"Created high-order memory for project {project_id}")
            
        except Exception as e:
            import logging
            logging.getLogger("Consolidation").error(f"LLM synthesis failed: {e}")
            self.db.rollback()
