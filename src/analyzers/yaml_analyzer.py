import yaml
from typing import Dict, Any, List


class YAMLAnalyzer:
    """
    Extracts lightweight pipeline / DAG relationships from YAML configs.
    Supports:
    - dbt manifest-style `nodes` with `depends_on.nodes`
    - dbt schema.yml-style `sources` and `models` with refs
    - simple Airflow-like DAGs expressed as task lists with upstream/downstream
    """

    def __init__(self):
        pass

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, "r") as f:
                content = yaml.safe_load(f)
            return self._analyze_config(content)
        except Exception as e:
            return {"error": str(e)}

    def _analyze_config(self, content: Any) -> Dict[str, Any]:
        results: Dict[str, Any] = {"pipelines": [], "dependencies": []}
        if not isinstance(content, dict):
            return results

        # dbt manifest style
        if "nodes" in content:
            for node_id, node_data in content["nodes"].items():
                results["pipelines"].append(
                    {
                        "id": node_id,
                        "type": node_data.get("resource_type"),
                        "depends_on": node_data.get("depends_on", {}).get("nodes", []),
                    }
                )

        # dbt schema.yml style: models and sources with dependencies via refs & sources
        if "models" in content and isinstance(content["models"], list):
            for model in content["models"]:
                name = model.get("name")
                if not name:
                    continue
                depends_on: List[str] = []
                for test in model.get("tests", []):
                    if isinstance(test, dict):
                        for v in test.values():
                            if isinstance(v, dict):
                                ref = v.get("ref")
                                if isinstance(ref, str):
                                    depends_on.append(ref)
                results["pipelines"].append(
                    {
                        "id": name,
                        "type": "model",
                        "depends_on": depends_on,
                    }
                )

        # Simple Airflow-style DAG definition: tasks list with upstream/downstream
        if "tasks" in content and isinstance(content["tasks"], list):
            for task in content["tasks"]:
                task_id = task.get("task_id") or task.get("id")
                if not task_id:
                    continue
                upstream = task.get("upstream_tasks") or task.get("upstream", [])
                downstream = task.get("downstream_tasks") or task.get("downstream", [])
                # Model pipeline node as the task itself, and dependencies as explicit edges
                results["pipelines"].append(
                    {
                        "id": task_id,
                        "type": "airflow_task",
                        "depends_on": upstream,
                    }
                )
                for u in upstream:
                    results["dependencies"].append({"source": u, "target": task_id})
                for d in downstream:
                    results["dependencies"].append({"source": task_id, "target": d})

        return results
