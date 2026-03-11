import argparse
import os
import json
from src.agents.surveyor import SurveyorAgent
from src.agents.hydrologist import HydrologistAgent

def main():
    parser = argparse.ArgumentParser(description="The Brownfield Cartographer - Repository Analysis CLI")
    parser.add_argument("repo_path", type=str, help="Path to the target repository to analyze")
    parser.add_argument("--output-dir", type=str, default="analysis_output", help="Directory to save analysis results")
    args = parser.parse_args()

    repo_path = args.repo_path
    output_dir = os.path.abspath(args.output_dir)
    
    # Check if repo_path is a GitHub URL
    if repo_path.startswith(("http://", "https://", "git@")):
        print(f"[*] Detecting remote repository: {repo_path}")
        temp_dir = os.path.join(output_dir, "cloned_repo")
        if os.path.exists(temp_dir):
            import shutil
            import stat
            def on_rm_error(func, path, exc_info):
                # path is the file that failed to be removed
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
            return

    repo_path = os.path.abspath(repo_path)

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    print(f"[*] Starting analysis of: {repo_path}")

    # 1. Run Surveyor Agent
    print("[*] Running Surveyor Agent...")
    surveyor = SurveyorAgent()
    survey_analysis = surveyor.run_analysis(repo_path)
    
    # Serialize Surveyor's Graph
    survey_graph_path = os.path.join(output_dir, "survey_graph.json")
    surveyor.storage.save_to_file(survey_graph_path)
    
    # Save Surveyor Metrics
    survey_metrics_path = os.path.join(output_dir, "survey_metrics.json")
    with open(survey_metrics_path, "w") as f:
        json.dump(survey_analysis, f, indent=2)

    # 2. Run Hydrologist Agent
    print("[*] Running Hydrologist Agent...")
    hydrologist = HydrologistAgent()
    
    # Look for files to build lineage
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            if file.endswith(".sql"):
                hydrologist.ingest_sql_file(file_path)
            elif file.endswith((".yaml", ".yml")):
                hydrologist.ingest_yaml_pipeline(file_path)
            elif file.endswith(".py"):
                hydrologist.ingest_python_file(file_path)
    
    # Serialize Hydrologist's Lineage Graph
    lineage_graph_path = os.path.join(output_dir, "lineage_graph.json")
    hydrologist.storage.save_to_file(lineage_graph_path)

    print(f"[*] Analysis complete!")
    print(f"[*] Results serialized to: {output_dir}")
    print(f"    - Module Graph: {survey_graph_path}")
    print(f"    - Lineage Graph: {lineage_graph_path}")
    print(f"    - Analytical Metrics: {survey_metrics_path}")

if __name__ == "__main__":
    main()
