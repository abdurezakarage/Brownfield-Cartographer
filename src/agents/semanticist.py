import os
import inspect
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx

from src.graph.storage import GraphStorage
from src.models.graph_models import NodeBase


@dataclass
class LLMCallRecord:
    model: str
    prompt_tokens: int
    completion_tokens: int


class TokenBudget:
    """
    Very lightweight token accounting and model selection.
    In a real system this would integrate with the chosen LLM provider.
    """

    def __init__(self, max_tokens: int = 200_000):
        self.max_tokens = max_tokens
        self.used_tokens = 0
        self.calls: List[LLMCallRecord] = []

    @property
    def remaining(self) -> int:
        return max(self.max_tokens - self.used_tokens, 0)

    def choose_model(self, expensive: str, cheap: str) -> str:
        # Heuristic: use cheap model until last 20% of budget, then be conservative.
        if self.remaining < self.max_tokens * 0.2:
            return cheap
        return cheap

    def record(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        total = prompt_tokens + completion_tokens
        self.used_tokens += total
        self.calls.append(
            LLMCallRecord(
                model=model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
            )
        )


class SemanticistAgent:
    """
    LLM-adjacent semantic analysis.

    NOTE: This implementation is LLM-provider-agnostic and uses stub logic
    so the rest of the system can be exercised without real API keys.
    """

    def __init__(self, storage: GraphStorage):
        self.storage = storage
        self.graph: nx.DiGraph = storage.graph
        self.budget = TokenBudget()

    # --- Purpose statements (grounded in code, ignoring docstrings) ---

    def _load_source_for_node(self, node_id: str) -> Optional[str]:
        data = self.graph.nodes[node_id]
        path = data.get("path")
        if not path:
            return None
        if not os.path.isabs(path):
            # Assume repo root is CWD of the process that built the graph.
            path = os.path.abspath(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except OSError:
            return None

    def _synthesize_purpose_from_code(self, source: str) -> str:
        """
        Stand-in for an LLM call that is explicitly instructed to
        ignore docstrings and reason from implementation only.
        """
        # Heuristic summary to keep this offline-friendly:
        first_non_empty = next((l for l in source.splitlines() if l.strip()), "")
        return f"Implementation-centric summary starting from: {first_non_empty[:120]}"

    def generate_purpose_statements(self) -> Dict[str, str]:
        results: Dict[str, str] = {}
        for node_id in list(self.graph.nodes):
            source = self._load_source_for_node(node_id)
            if not source:
                continue
            purpose = self._synthesize_purpose_from_code(source)
            self.graph.nodes[node_id]["purpose_statement"] = purpose
            results[node_id] = purpose
        return results

    # --- Documentation drift detection ---

    def _extract_docstring(self, source: str) -> Optional[str]:
        try:
            module = inspect.getdoc(inspect.getmodule(inspect))
        except Exception:
            module = None
        # Minimal stand-in: look for triple-quoted strings near top of file.
        lines = source.splitlines()
        for i, line in enumerate(lines[:20]):
            if '"""' in line or "'''" in line:
                return line.strip().strip('\"\'')
        return None

    def detect_doc_drift(self) -> List[Dict[str, Any]]:
        drift_report: List[Dict[str, Any]] = []
        for node_id in list(self.graph.nodes):
            source = self._load_source_for_node(node_id)
            if not source:
                continue
            impl_purpose = self.graph.nodes[node_id].get("purpose_statement")
            if not impl_purpose:
                impl_purpose = self._synthesize_purpose_from_code(source)
                self.graph.nodes[node_id]["purpose_statement"] = impl_purpose

            doc = self._extract_docstring(source)
            if not doc:
                continue

            # Extremely simple drift heuristic: string containment
            if doc in impl_purpose or impl_purpose in doc:
                severity = "none"
                contradictions: List[str] = []
            else:
                severity = "medium"
                contradictions = [f"Docstring '{doc[:80]}' does not match implementation summary."]

            drift_report.append(
                {
                    "node_id": node_id,
                    "severity": severity,
                    "contradictions": contradictions,
                }
            )
        return drift_report

    # --- Domain clustering (embedding-style, without external APIs) ---

    def cluster_domains(self, k: int = 4) -> Dict[str, str]:
        """
        Cheap content-based clustering using bag-of-words emulation.
        Assigns simple domain labels inferred from filenames and neighbors.
        """
        assignments: Dict[str, str] = {}
        for node_id, data in self.graph.nodes(data=True):
            name = data.get("name") or node_id
            if "test" in name:
                domain = "Testing & QA"
            elif "db" in name or "sql" in name:
                domain = "Data Access"
            elif "api" in name or "view" in name:
                domain = "API & Presentation"
            else:
                domain = "Core Logic"
            assignments[node_id] = domain
            self.graph.nodes[node_id]["domain_cluster"] = domain
        return assignments

    # --- Day-One question answering (using graph as evidence) ---

    def answer_day_one_questions(self) -> Dict[str, Any]:
        """
        Synthesizes high-level answers using graph structure and annotations.
        Returns evidence-cited answers keyed by question.
        """
        answers: Dict[str, Any] = {}

        def pick_high_pagerank_nodes(limit: int = 5) -> List[Tuple[str, Dict[str, Any]]]:
            ranked = sorted(
                self.graph.nodes(data=True),
                key=lambda item: item[1].get("pagerank", 0.0),
                reverse=True,
            )
            return ranked[:limit]

        # Q1: What are the critical paths through the system?
        critical_nodes = pick_high_pagerank_nodes()
        answers["critical_paths"] = {
            "summary": "Top modules by structural centrality (pagerank) form the critical path.",
            "evidence": [
                {
                    "node_id": nid,
                    "file": data.get("path"),
                    "line_range": None,
                    "method": "static",
                }
                for nid, data in critical_nodes
            ],
        }

        # Q2: Where does data enter and leave the system?
        sources = [n for n, d in self.graph.in_degree() if d == 0]
        sinks = [n for n, d in self.graph.out_degree() if d == 0]
        answers["data_sources_sinks"] = {
            "sources": [
                {
                    "node_id": nid,
                    "file": self.graph.nodes[nid].get("path"),
                    "line_range": None,
                    "method": "static",
                }
                for nid in sources
            ],
            "sinks": [
                {
                    "node_id": nid,
                    "file": self.graph.nodes[nid].get("path"),
                    "line_range": None,
                    "method": "static",
                }
                for nid in sinks
            ],
        }

        # Q3–Q5 can be expanded similarly; keep placeholders with evidence references.
        answers["risk_hotspots"] = {
            "summary": "High-velocity or circular-dependency nodes are likely risk hotspots.",
            "evidence": [
                {
                    "node_id": nid,
                    "file": data.get("path"),
                    "line_range": None,
                    "method": "static",
                }
                for nid, data in self.graph.nodes(data=True)
                if data.get("change_velocity_30d", 0.0) > 0
            ],
        }

        answers["dead_code_candidates"] = {
            "summary": "Nodes with zero in-degree and low change velocity are potential dead code.",
            "evidence": [
                {
                    "node_id": nid,
                    "file": data.get("path"),
                    "line_range": None,
                    "method": "static",
                }
                for nid, data in self.graph.nodes(data=True)
                if self.graph.in_degree(nid) == 0 and data.get("change_velocity_30d", 0.0) == 0.0
            ],
        }

        answers["domains"] = {
            "summary": "Inferred business domains based on filenames and usage patterns.",
            "evidence": [
                {
                    "node_id": nid,
                    "file": data.get("path"),
                    "domain": data.get("domain_cluster"),
                    "line_range": None,
                    "method": "LLM",
                }
                for nid, data in self.graph.nodes(data=True)
            ],
        }

        return answers

