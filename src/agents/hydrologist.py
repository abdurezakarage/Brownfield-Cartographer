import networkx as nx
from typing import Set, List, Dict, Any
from src.graph.storage import GraphStorage
from src.models.graph_models import NodeBase, EdgeBase, NodeType, EdgeType
from src.analyzers.yaml_analyzer import YAMLAnalyzer
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer
from src.analyzers.sql_analyzer import SQLAnalyzer

class HydrologistAgent:
    def __init__(self):
        self.storage = GraphStorage()
        self.sql_analyzer = SQLAnalyzer()
        self.yaml_analyzer = YAMLAnalyzer()
        self.python_analyzer = TreeSitterAnalyzer()

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
                    type=EdgeType.DEPENDS_ON, # Changed from FLOWS_TO to match EdgeType
                    properties={
                        "transformation_type": "SQL",
                        "source_file": file_path
                    }
                ))

    def ingest_python_file(self, file_path: str):
        analysis = self.python_analyzer.parse_file(file_path)
        if "error" in analysis:
            return
            
        file_node_id = os.path.basename(file_path)
        for func in analysis.get("functions", []):
            if func["name"]:
                func_id = f"{file_node_id}::{func['name']}"
                self.storage.add_node(NodeBase(
                    id=func_id,
                    type=NodeType.FUNCTION,
                    name=func["name"],
                    path=file_path
                ))
                # Simplification: Assume functions in same file flow to each other if called
                # In a real tool, we'd look for calls.
                
    def ingest_yaml_pipeline(self, file_path: str):
        analysis = self.yaml_analyzer.parse_file(file_path)
        if "error" in analysis:
            return
            
        for pipe in analysis.get("pipelines", []):
            self.storage.add_node(NodeBase(
                id=pipe["id"],
                type=NodeType.MODULE,
                name=pipe["id"]
            ))
            for dep in pipe.get("depends_on", []):
                self.storage.add_edge(EdgeBase(
                    source=dep,
                    target=pipe["id"],
                    type=EdgeType.DEPENDS_ON,
                    properties={"source_file": file_path}
                ))

    def blast_radius(self, node_id: str) -> List[Dict[str, Any]]:
        """Identifies all downstream components affected by a change to node_id with paths."""
        if node_id not in self.storage.graph:
            return []
        
        descendants = nx.descendants(self.storage.graph, node_id)
        results = []
        for desc in descendants:
            path = nx.shortest_path(self.storage.graph, node_id, desc)
            results.append({
                "id": desc,
                "path": path
            })
        return results

    def find_sources(self) -> List[str]:
        """Identifies entry points (nodes with no inbound edges)."""
        return [n for n, d in self.storage.graph.in_degree() if d == 0]

    def find_sinks(self) -> List[str]:
        """Identifies end-of-line consumers (nodes with no outbound edges)."""
        return [n for n, d in self.storage.graph.out_degree() if d == 0]
    
    def get_lineage_graph(self) -> nx.DiGraph:
        return self.storage.graph
