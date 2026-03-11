import networkx as nx
from typing import Set, List, Dict, Any
from src.graph.storage import GraphStorage
from src.models.graph_models import NodeBase, EdgeBase, NodeType, EdgeType
from src.analyzers.sql_analyzer import SQLAnalyzer

class HydrologistAgent:
    def __init__(self):
        self.storage = GraphStorage()
        self.sql_analyzer = SQLAnalyzer()

    def ingest_sql_file(self, file_path: str):
        analysis = self.sql_analyzer.analyze_file(file_path)
        if "error" in analysis:
            return

        for source in analysis["sources"]:
            self.storage.add_node(NodeBase(
                id=source,
                type=NodeType.TABLE,
                name=source
            ))
            for target in analysis["targets"]:
                self.storage.add_node(NodeBase(
                    id=target,
                    type=NodeType.TABLE,
                    name=target
                ))
                self.storage.add_edge(EdgeBase(
                    source=source,
                    target=target,
                    type=EdgeType.FLOWS_TO
                ))

    def blast_radius(self, node_id: str) -> Set[str]:
        """Identifies all downstream components affected by a change to node_id."""
        if node_id not in self.storage.graph:
            return set()
        return nx.descendants(self.storage.graph, node_id)

    def find_sources(self, node_id: str) -> Set[str]:
        """Identifies all upstream data sources for a given node."""
        if node_id not in self.storage.graph:
            return set()
        return nx.ancestors(self.storage.graph, node_id)

    def find_sinks(self) -> List[str]:
        """Identifies end-of-line data consumers (nodes with no outbound flow)."""
        return [
            n for n, d in self.storage.graph.out_degree() 
            if d == 0 and self.storage.graph.nodes[n].get('type') == NodeType.TABLE
        ]
    
    def get_lineage_graph(self) -> nx.DiGraph:
        return self.storage.graph
