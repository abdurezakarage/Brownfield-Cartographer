import os
import networkx as nx
from typing import List, Dict, Any

from src.graph.storage import GraphStorage
from src.models.graph_models import NodeBase, EdgeBase, NodeType, EdgeType
from src.analyzers.yaml_analyzer import YAMLAnalyzer
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer
from src.analyzers.sql_analyzer import SQLAnalyzer
from src.analyzers.python_dataflow_analyzer import PythonDataflowAnalyzer


class DataLineageGraph:
    """
    Thin wrapper around GraphStorage exposing lineage-centric helpers.
    """

    def __init__(self, storage: GraphStorage):
        self._storage = storage

    @property
    def graph(self) -> nx.DiGraph:
        return self._storage.graph

    def blast_radius(self, node_id: str) -> List[Dict[str, Any]]:
        if node_id not in self.graph:
            return []
        descendants = nx.descendants(self.graph, node_id)
        results = []
        for desc in descendants:
            path = nx.shortest_path(self.graph, node_id, desc)
            results.append({"id": desc, "path": path})
        return results

    def find_sources(self) -> List[str]:
        return [n for n, d in self.graph.in_degree() if d == 0]

    def find_sinks(self) -> List[str]:
        return [n for n, d in self.graph.out_degree() if d == 0]


class HydrologistAgent:
    def __init__(self):
        self.storage = GraphStorage()
        self.lineage = DataLineageGraph(self.storage)
        self.sql_analyzer = SQLAnalyzer()
        self.yaml_analyzer = YAMLAnalyzer()
        self.python_structure_analyzer = TreeSitterAnalyzer()
        self.python_dataflow = PythonDataflowAnalyzer()

    def ingest_sql_file(self, file_path: str):
        analysis = self.sql_analyzer.analyze_file(file_path)
        if "error" in analysis:
            return

        for source in analysis["sources"]:
            self.storage.add_node(
                NodeBase(
                    id=source,
                    type=NodeType.TABLE,
                    name=source,
                    properties={"source_file": file_path},
                )
            )
            for target in analysis["targets"]:
                self.storage.add_node(
                    NodeBase(
                        id=target,
                        type=NodeType.TABLE,
                        name=target,
                        properties={"source_file": file_path},
                    )
                )
                self.storage.add_edge(
                    EdgeBase(
                        source=source,
                        target=target,
                        type=EdgeType.DEPENDS_ON,
                        properties={
                            "transformation_type": "SQL",
                            "source_file": file_path,
                            "dialect": analysis.get("dialect"),
                            "line_range": None,
                        },
                    )
                )

    def ingest_python_file(self, file_path: str):
        # Structural info (functions/classes)
        struct = self.python_structure_analyzer.parse_file(file_path)
        if "error" in struct:
            struct = {"functions": []}

        file_node_id = os.path.basename(file_path)
        for func in struct.get("functions", []):
            if func.get("name"):
                func_id = f"{file_node_id}::{func['name']}"
                self.storage.add_node(
                    NodeBase(
                        id=func_id,
                        type=NodeType.FUNCTION,
                        name=func["name"],
                        path=file_path,
                    )
                )

        # Dataflow info (pandas / pyspark / sqlalchemy)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError:
            return

        flow = self.python_dataflow.analyze(source, filename=file_path)
        for read in flow.get("reads", []):
            table = read["table"] or f"<dynamic:{read['engine']}>"
            self.storage.add_node(
                NodeBase(
                    id=table,
                    type=NodeType.TABLE,
                    name=table,
                    properties={"source_file": file_path},
                )
            )
            self.storage.add_edge(
                EdgeBase(
                    source=table,
                    target=file_node_id,
                    type=EdgeType.READS,
                    properties={
                        "transformation_type": read["engine"],
                        "operation": read["operation"],
                        "source_file": file_path,
                        "line_range": (read.get("lineno"), read.get("end_lineno")),
                        "dynamic_reference": read["is_dynamic"],
                    },
                )
            )

        for write in flow.get("writes", []):
            table = write["table"] or f"<dynamic:{write['engine']}>"
            self.storage.add_node(
                NodeBase(
                    id=table,
                    type=NodeType.TABLE,
                    name=table,
                    properties={"source_file": file_path},
                )
            )
            self.storage.add_edge(
                EdgeBase(
                    source=file_node_id,
                    target=table,
                    type=EdgeType.WRITES,
                    properties={
                        "transformation_type": write["engine"],
                        "operation": write["operation"],
                        "source_file": file_path,
                        "line_range": (write.get("lineno"), write.get("end_lineno")),
                        "dynamic_reference": write["is_dynamic"],
                    },
                )
            )

    def ingest_yaml_pipeline(self, file_path: str):
        analysis = self.yaml_analyzer.parse_file(file_path)
        if "error" in analysis:
            return

        for pipe in analysis.get("pipelines", []):
            pipe_id = pipe.get("id")
            if not pipe_id:
                continue
            self.storage.add_node(
                NodeBase(
                    id=pipe_id,
                    type=NodeType.MODULE,
                    name=pipe_id,
                    properties={"source_file": file_path},
                )
            )
            for dep in pipe.get("depends_on", []):
                self.storage.add_edge(
                    EdgeBase(
                        source=dep,
                        target=pipe_id,
                        type=EdgeType.DEPENDS_ON,
                        properties={
                            "transformation_type": "config",
                            "source_file": file_path,
                            "line_range": None,
                        },
                    )
                )

        # Also ingest explicit dependencies, if present
        for dep in analysis.get("dependencies", []):
            src = dep.get("source")
            tgt = dep.get("target")
            if not src or not tgt:
                continue
            self.storage.add_edge(
                EdgeBase(
                    source=src,
                    target=tgt,
                    type=EdgeType.DEPENDS_ON,
                    properties={
                        "transformation_type": "config",
                        "source_file": file_path,
                        "line_range": None,
                    },
                )
            )

    # Backwards-compatible helpers that delegate to DataLineageGraph

    def blast_radius(self, node_id: str) -> List[Dict[str, Any]]:
        """Identifies all downstream components affected by a change to node_id with paths."""
        return self.lineage.blast_radius(node_id)

    def find_sources(self) -> List[str]:
        """Identifies entry points (nodes with no inbound edges)."""
        return self.lineage.find_sources()

    def find_sinks(self) -> List[str]:
        """Identifies end-of-line consumers (nodes with no outbound edges)."""
        return self.lineage.find_sinks()

    def get_lineage_graph(self) -> nx.DiGraph:
        return self.lineage.graph
