from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import networkx as nx

from src.graph.storage import GraphStorage


@dataclass
class QueryResult:
    answer: str
    evidence: List[Dict[str, Any]]


class NavigatorAgent:
    """
    Simple query interface over the knowledge graph.
    Implements the four rubric tools in a graph-grounded way.
    """

    def __init__(self, storage: GraphStorage):
        self.storage = storage
        self.graph: nx.DiGraph = storage.graph

    # Tool 1: find_implementation(concept)
    def find_implementation(self, concept: str) -> QueryResult:
        # Cheap vector-ish search: fuzzy match over node name and purpose.
        matches: List[Dict[str, Any]] = []
        for nid, data in self.graph.nodes(data=True):
            haystack = f"{data.get('name','')} {data.get('purpose_statement','')}".lower()
            if concept.lower() in haystack:
                matches.append(
                    {
                        "node_id": nid,
                        "file": data.get("path"),
                        "line_range": None,
                        "method": "LLM",
                    }
                )
        if not matches:
            return QueryResult(
                answer=f"No implementation found for concept '{concept}'.",
                evidence=[],
            )
        return QueryResult(
            answer=f"Found {len(matches)} candidate implementations for '{concept}'.",
            evidence=matches[:10],
        )

    # Tool 2: trace_lineage(dataset, direction)
    def trace_lineage(self, dataset: str, direction: str = "downstream") -> QueryResult:
        if dataset not in self.graph:
            return QueryResult(
                answer=f"Dataset node '{dataset}' not found in lineage graph.",
                evidence=[],
            )

        if direction == "upstream":
            nodes = nx.ancestors(self.graph, dataset)
        else:
            nodes = nx.descendants(self.graph, dataset)

        evidence: List[Dict[str, Any]] = []
        for nid in nodes:
            data = self.graph.nodes[nid]
            evidence.append(
                {
                    "node_id": nid,
                    "file": data.get("path"),
                    "line_range": None,
                    "method": "static",
                }
            )
        return QueryResult(
            answer=f"Found {len(nodes)} {'upstream' if direction=='upstream' else 'downstream'} lineage nodes for '{dataset}'.",
            evidence=evidence[:25],
        )

    # Tool 3: blast_radius(module_path)
    def blast_radius(self, module_path: str) -> QueryResult:
        if module_path not in self.graph:
            return QueryResult(
                answer=f"Module '{module_path}' not found in module graph.",
                evidence=[],
            )
        descendants = nx.descendants(self.graph, module_path)
        evidence: List[Dict[str, Any]] = []
        for nid in descendants:
            data = self.graph.nodes[nid]
            evidence.append(
                {
                    "node_id": nid,
                    "file": data.get("path"),
                    "line_range": None,
                    "method": "static",
                }
            )
        return QueryResult(
            answer=f"Blast radius for '{module_path}' includes {len(descendants)} dependent nodes.",
            evidence=evidence[:25],
        )

    # Tool 4: explain_module(path)
    def explain_module(self, path: str) -> QueryResult:
        if path not in self.graph:
            return QueryResult(
                answer=f"Module '{path}' not found.",
                evidence=[],
            )

        data = self.graph.nodes[path]
        neighbors = list(self.graph.successors(path)) + list(self.graph.predecessors(path))
        explanation = (
            f"Module '{path}' participates in {len(neighbors)} relationships. "
            f"Domain: {data.get('domain_cluster')}. "
            f"Purpose: {data.get('purpose_statement') or 'unknown'}."
        )
        evidence: List[Dict[str, Any]] = [
            {
                "node_id": path,
                "file": data.get("path"),
                "line_range": None,
                "method": "LLM",
            }
        ]
        for nid in neighbors[:20]:
            nd = self.graph.nodes[nid]
            evidence.append(
                {
                    "node_id": nid,
                    "file": nd.get("path"),
                    "line_range": None,
                    "method": "static",
                }
            )
        return QueryResult(answer=explanation, evidence=evidence)

