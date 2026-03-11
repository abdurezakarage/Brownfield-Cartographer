import networkx as nx
import os
import subprocess
from typing import Dict, List, Any
from src.graph.storage import GraphStorage
from src.models.graph_models import NodeBase, EdgeBase, NodeType, EdgeType
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer

class SurveyorAgent:
    def __init__(self):
        self.storage = GraphStorage()
        self.analyzer = TreeSitterAnalyzer()

    def survey_repository(self, repo_path: str):
        """Builds a module graph from import relationships."""
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(('.py', '.js', '.ts')):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path)
                    
                    # Add file node
                    self.storage.add_node(NodeBase(
                        id=rel_path,
                        type=NodeType.FILE,
                        name=file,
                        path=rel_path
                    ))
                    
                    # Parse for imports
                    analysis = self.analyzer.parse_file(file_path)
                    for imp in analysis.get("imports", []):
                        # Simplified import resolution
                        # In reality, would need to map import string to file path
                        self.storage.add_edge(EdgeBase(
                            source=rel_path,
                            target=imp, # Placeholder for resolved target
                            type=EdgeType.IMPORTS
                        ))

    def get_pagerank(self) -> Dict[str, float]:
        if not self.storage.graph.nodes:
            return {}
        return nx.pagerank(self.storage.graph)

    def analyze_git_velocity(self, repo_path: str) -> Dict[str, int]:
        try:
            result = subprocess.run(
                ["git", "log", "--name-only", "--pretty=format:"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            velocity = {}
            for line in result.stdout.splitlines():
                if line.strip():
                    file = line.strip()
                    velocity[file] = velocity.get(file, 0) + 1
            return velocity
        except Exception:
            return {}

    def detect_dead_code_candidates(self) -> List[str]:
        """Nodes with zero in-degree are potential dead code."""
        candidates = [
            n for n, d in self.storage.graph.in_degree() 
            if d == 0 and self.storage.graph.nodes[n].get('type') == NodeType.FILE
        ]
        return candidates

    def run_analysis(self, repo_path: str) -> Dict[str, Any]:
        self.survey_repository(repo_path)
        return {
            "pagerank": self.get_pagerank(),
            "velocity": self.analyze_git_velocity(repo_path),
            "dead_code": self.detect_dead_code_candidates()
        }
