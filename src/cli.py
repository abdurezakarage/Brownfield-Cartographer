import argparse
import os
import json

from src.orchestrator import run_full_pipeline
from src.graph.storage import GraphStorage
from src.agents.navigator import NavigatorAgent


def _resolve_repo(repo_path: str, output_dir: str) -> str:
    # Check if repo_path is a GitHub URL
    if repo_path.startswith(("http://", "https://", "git@")):
        print(f"[*] Detecting remote repository: {repo_path}")
        temp_dir = os.path.join(output_dir, "cloned_repo")
        if os.path.exists(temp_dir):
            import shutil
            import stat

            def on_rm_error(func, path, exc_info):
                os.chmod(path, stat.S_IWRITE)
                func(path)

            shutil.rmtree(temp_dir, onerror=on_rm_error)

        import subprocess

        print(f"[*] Cloning repository to {temp_dir}...")
        try:
            subprocess.run(["git", "clone", repo_path, temp_dir], check=True)
            repo_path = temp_dir
        except subprocess.CalledProcessError as e:
            print(f"[!] Error cloning repository: {e}")
            raise
    return os.path.abspath(repo_path)


def cmd_analyze(args: argparse.Namespace) -> None:
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    repo_path = _resolve_repo(args.repo_path, output_dir)

    cartography_dir = os.path.join(repo_path, ".cartography")
    print(f"[*] Running full analysis pipeline on: {repo_path}")
    results = run_full_pipeline(repo_path, cartography_dir)
    print(f"[*] Analysis complete. Outputs in {cartography_dir}")
    for k, v in results.items():
        print(f"    - {k}: {v}")


def cmd_query(args: argparse.Namespace) -> None:
    repo_path = os.path.abspath(args.repo_path)
    cartography_dir = os.path.join(repo_path, ".cartography")
    graph_path = os.path.join(cartography_dir, "knowledge_graph.json")
    if not os.path.exists(graph_path):
        print(f"[!] No knowledge graph found at {graph_path}. Run 'analyze' first.")
        return

    storage = GraphStorage()
    with open(graph_path, "r", encoding="utf-8") as f:
        storage.deserialize(f.read())
    navigator = NavigatorAgent(storage)

    print("[*] Entering Navigator interactive mode. Type 'exit' to quit.")
    while True:
        try:
            line = input("nav> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not line or line.lower() in {"exit", "quit"}:
            break

        # Naive routing: infer which tool to use by prefix
        if line.startswith("find "):
            concept = line[len("find ") :].strip()
            res = navigator.find_implementation(concept)
        elif line.startswith("lineage "):
            parts = line.split()
            dataset = parts[1]
            direction = parts[2] if len(parts) > 2 else "downstream"
            res = navigator.trace_lineage(dataset, direction=direction)
        elif line.startswith("blast "):
            module = line[len("blast ") :].strip()
            res = navigator.blast_radius(module)
        elif line.startswith("explain "):
            path = line[len("explain ") :].strip()
            res = navigator.explain_module(path)
        else:
            print("Unrecognized command. Use: find|lineage|blast|explain.")
            continue

        print(res.answer)
        for ev in res.evidence[:5]:
            print(
                f"  - {ev.get('node_id')} ({ev.get('file')}), "
                f"line_range={ev.get('line_range')}, method={ev.get('method')}"
            )


def main():
    parser = argparse.ArgumentParser(
        description="The Brownfield Cartographer - Repository Analysis CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_p = subparsers.add_parser("analyze", help="Run full analysis pipeline")
    analyze_p.add_argument("repo_path", type=str, help="Path or GitHub URL to analyze")
    analyze_p.add_argument(
        "--output-dir",
        type=str,
        default="analysis_output",
        help="Directory to use for cloning remote repos (if needed)",
    )
    analyze_p.set_defaults(func=cmd_analyze)

    query_p = subparsers.add_parser("query", help="Interactive Navigator mode")
    query_p.add_argument(
        "repo_path",
        type=str,
        help="Local path to an already-analyzed repository",
    )
    query_p.set_defaults(func=cmd_query)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
