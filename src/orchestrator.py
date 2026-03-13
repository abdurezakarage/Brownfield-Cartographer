import json
import os
import subprocess
from typing import Any, Dict, List, Tuple

from src.agents.surveyor import SurveyorAgent
from src.agents.hydrologist import HydrologistAgent
from src.agents.semanticist import SemanticistAgent
from src.agents.archivist import ArchivistAgent
from src.graph.storage import GraphStorage


def _get_latest_commit(repo_path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return ""


def _get_changed_files_since(repo_path: str, since_commit: str) -> List[str]:
    if not since_commit:
        return []
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{since_commit}..HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def run_full_pipeline(repo_path: str, cartography_dir: str) -> Dict[str, Any]:
    os.makedirs(cartography_dir, exist_ok=True)

    metadata_path = os.path.join(cartography_dir, "metadata.json")
    previous_commit = ""
    if os.path.exists(metadata_path):
        with open(metadata_path, "r", encoding="utf-8") as f:
            try:
                previous_commit = json.load(f).get("last_commit", "")
            except Exception:
                previous_commit = ""

    latest_commit = _get_latest_commit(repo_path)
    changed_files = _get_changed_files_since(repo_path, previous_commit)

    # --- Surveyor ---
    surveyor = SurveyorAgent()
    survey_metrics = surveyor.run_analysis(repo_path)
    survey_graph_path = os.path.join(cartography_dir, "survey_graph.json")
    surveyor.storage.save_to_file(survey_graph_path)

    with open(os.path.join(cartography_dir, "survey_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(survey_metrics, f, indent=2)

    # --- Hydrologist ---
    hydrologist = HydrologistAgent()
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel = os.path.relpath(file_path, repo_path).replace("\\", "/")
            if changed_files and rel not in changed_files:
                continue
            if file.endswith(".sql"):
                hydrologist.ingest_sql_file(file_path)
            elif file.endswith((".yaml", ".yml")):
                hydrologist.ingest_yaml_pipeline(file_path)
            elif file.endswith(".py"):
                hydrologist.ingest_python_file(file_path)

    lineage_graph_path = os.path.join(cartography_dir, "lineage_graph.json")
    hydrologist.storage.save_to_file(lineage_graph_path)

    # --- Merge graphs into a unified storage for semanticist/navigator ---
    unified_storage = GraphStorage()
    # Load surveyor graph
    unified_storage.deserialize(open(survey_graph_path, "r", encoding="utf-8").read())
    # Merge hydrologist graph
    for nid, data in hydrologist.storage.graph.nodes(data=True):
        unified_storage.graph.add_node(nid, **data)
    for u, v, data in hydrologist.storage.graph.edges(data=True):
        unified_storage.graph.add_edge(u, v, **data)

    # --- Semanticist ---
    semanticist = SemanticistAgent(unified_storage)
    semanticist.generate_purpose_statements()
    drift = semanticist.detect_doc_drift()
    domains = semanticist.cluster_domains()
    day_one = semanticist.answer_day_one_questions()

    with open(os.path.join(cartography_dir, "semantic_drift.json"), "w", encoding="utf-8") as f:
        json.dump(drift, f, indent=2)
    with open(os.path.join(cartography_dir, "domain_clusters.json"), "w", encoding="utf-8") as f:
        json.dump(domains, f, indent=2)
    with open(os.path.join(cartography_dir, "day_one_answers.json"), "w", encoding="utf-8") as f:
        json.dump(day_one, f, indent=2)

    # Persist unified graph
    unified_graph_path = os.path.join(cartography_dir, "knowledge_graph.json")
    unified_storage.save_to_file(unified_graph_path)

    # --- Archivist ---
    archivist = ArchivistAgent(cartography_dir)
    archivist.generate_codebase_md(unified_storage)
    archivist.generate_onboarding_brief(day_one)

    # --- Metadata / incremental bookkeeping ---
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump({"last_commit": latest_commit}, f, indent=2)

    return {
        "survey_graph": survey_graph_path,
        "lineage_graph": lineage_graph_path,
        "knowledge_graph": unified_graph_path,
        "day_one_answers": os.path.join(cartography_dir, "day_one_answers.json"),
    }

