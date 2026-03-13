import json
import os
from datetime import datetime
from typing import Any, Dict, List

from src.graph.storage import GraphStorage


class ArchivistAgent:
    """
    Consumes the serialized knowledge graph and semantic outputs
    to generate CODEBASE.md, onboarding_brief.md, and cartography_trace.jsonl.
    """

    def __init__(self, cartography_dir: str):
        self.cartography_dir = cartography_dir
        self.trace_path = os.path.join(cartography_dir, "cartography_trace.jsonl")

    # --- Trace logging ---

    def _log_trace(
        self,
        agent: str,
        action: str,
        evidence_sources: List[str],
        confidence: float,
        method: str,
    ) -> None:
        record = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "agent": agent,
            "action": action,
            "evidence_sources": evidence_sources,
            "confidence": confidence,
            "analysis_method": method,
        }
        os.makedirs(self.cartography_dir, exist_ok=True)
        with open(self.trace_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    # --- CODEBASE.md generation ---

    def generate_codebase_md(self, storage: GraphStorage) -> str:
        g = storage.graph
        lines: List[str] = []

        lines.append("## Architecture Overview")
        lines.append("")
        lines.append("High-level module graph derived from static import relationships.")
        lines.append("")

        lines.append("## Critical Path")
        lines.append("")
        critical = sorted(
            g.nodes(data=True),
            key=lambda item: item[1].get("pagerank", 0.0),
            reverse=True,
        )[:10]
        for nid, data in critical:
            lines.append(f"- `{nid}` (pagerank={data.get('pagerank', 0.0):.4f})")
        lines.append("")

        lines.append("## Data Sources & Sinks")
        lines.append("")
        sources = [n for n, d in g.in_degree() if d == 0]
        sinks = [n for n, d in g.out_degree() if d == 0]
        lines.append("### Sources")
        for nid in sources:
            lines.append(f"- `{nid}`")
        lines.append("")
        lines.append("### Sinks")
        for nid in sinks:
            lines.append(f"- `{nid}`")
        lines.append("")

        lines.append("## Known Debt")
        lines.append("")
        for nid, data in g.nodes(data=True):
            if data.get("is_dead_code_candidate"):
                lines.append(f"- Potential dead code: `{nid}`")
        lines.append("")

        lines.append("## High-Velocity Files")
        lines.append("")
        high_vel = [
            (nid, data)
            for nid, data in g.nodes(data=True)
            if data.get("change_velocity_30d", 0.0) > 0
        ]
        for nid, data in high_vel:
            lines.append(
                f"- `{nid}` (changes_30d={data.get('change_velocity_30d', 0.0)})"
            )
        lines.append("")

        lines.append("## Module Purpose Index")
        lines.append("")
        for nid, data in g.nodes(data=True):
            purpose = data.get("purpose_statement")
            if purpose:
                lines.append(f"- `{nid}`: {purpose}")
        lines.append("")

        content = "\n".join(lines)
        out_path = os.path.join(self.cartography_dir, "CODEBASE.md")
        os.makedirs(self.cartography_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

        self._log_trace(
            agent="Archivist",
            action="generate_CODEBASE_md",
            evidence_sources=["survey_graph", "lineage_graph"],
            confidence=0.9,
            method="static",
        )
        return out_path

    # --- Onboarding brief generation ---

    def generate_onboarding_brief(self, day_one_answers: Dict[str, Any]) -> str:
        lines: List[str] = []
        lines.append("# Onboarding Brief")
        lines.append("")

        for key, payload in day_one_answers.items():
            lines.append(f"## {key.replace('_', ' ').title()}")
            summary = payload.get("summary")
            if summary:
                lines.append(summary)
            evidence = payload.get("evidence") or []
            if evidence:
                lines.append("")
                lines.append("Evidence:")
                for ev in evidence[:10]:
                    lines.append(
                        f"- {ev.get('node_id')} ({ev.get('file')}), "
                        f"line_range={ev.get('line_range')}, method={ev.get('method')}"
                    )
            lines.append("")

        out_path = os.path.join(self.cartography_dir, "onboarding_brief.md")
        os.makedirs(self.cartography_dir, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        self._log_trace(
            agent="Archivist",
            action="generate_onboarding_brief",
            evidence_sources=["semanticist_day_one"],
            confidence=0.9,
            method="LLM",
        )
        return out_path

