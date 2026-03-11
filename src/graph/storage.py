import networkx as nx
import json
from typing import List, Optional
from src.models.graph_models import NodeBase, EdgeBase, KnowledgeGraphData

class GraphStorage:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_node(self, node: NodeBase):
        # Extract properties that are not part of the standard fields
        extra_props = node.properties.copy()
        self.graph.add_node(
            node.id, 
            type=node.type, 
            name=node.name, 
            path=node.path, 
            **extra_props
        )

    def add_edge(self, edge: EdgeBase):
        extra_props = edge.properties.copy()
        self.graph.add_edge(
            edge.source, 
            edge.target, 
            type=edge.type, 
            **extra_props
        )

    def serialize(self) -> str:
        nodes = []
        for n, d in self.graph.nodes(data=True):
            reserved = ["type", "name", "path"]
            properties = {k: v for k, v in d.items() if k not in reserved}
            nodes.append(NodeBase(
                id=str(n),
                type=d.get("type"),
                name=d.get("name"),
                path=d.get("path"),
                properties=properties
            ))
        
        edges = []
        for u, v, d in self.graph.edges(data=True):
            reserved = ["type"]
            properties = {k: v for k, v in d.items() if k not in reserved}
            edges.append(EdgeBase(
                source=str(u),
                target=str(v),
                type=d.get("type"),
                properties=properties
            ))
        
        data = KnowledgeGraphData(nodes=nodes, edges=edges)
        if hasattr(data, "model_dump_json"):
            return data.model_dump_json(indent=2)
        return data.json(indent=2)

    def deserialize(self, json_data: str):
        if hasattr(KnowledgeGraphData, "model_validate_json"):
            data = KnowledgeGraphData.model_validate_json(json_data)
        else:
            data = KnowledgeGraphData.parse_raw(json_data)
            
        self.graph = nx.DiGraph()
        for node in data.nodes:
            self.add_node(node)
        for edge in data.edges:
            self.add_edge(edge)

    def save_to_file(self, file_path: str):
        with open(file_path, "w") as f:
            f.write(self.serialize())

    def load_from_file(self, file_path: str):
        with open(file_path, "r") as f:
            self.deserialize(f.read())
