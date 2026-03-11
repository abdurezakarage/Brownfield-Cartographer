import networkx as nx
import os
import subprocess
from typing import Dict, List, Any, Optional
from src.graph.storage import GraphStorage
from src.models.graph_models import NodeBase, EdgeBase, NodeType, EdgeType
from src.analyzers.tree_sitter_analyzer import TreeSitterAnalyzer

class SurveyorAgent:
    def __init__(self):
        self.storage = GraphStorage()
        self.analyzer = TreeSitterAnalyzer()

    def resolve_import(self, import_str: str, base_dir: str, current_file_path: str) -> Optional[str]:
        """Resolves a python import string to a relative file path."""
        # This is a simplified resolver 
        parts = import_str.split('.')
        # Check for relative imports
        if import_str.startswith('.'):
            # Very basic handling of relative imports
            return None 
        
        # Check potential file paths
        potential_rel_path = os.path.join(*parts) + ".py"
        full_path = os.path.join(base_dir, potential_rel_path)
        
        if os.path.exists(full_path):
            return os.path.relpath(full_path, base_dir)
        
        # Check if it's a directory (init file)
        potential_dir_path = os.path.join(*parts, "__init__.py")
        full_dir_path = os.path.join(base_dir, potential_dir_path)
        if os.path.exists(full_dir_path):
            return os.path.relpath(full_dir_path, base_dir)
            
        return None

    def survey_repository(self, repo_path: str):
        """Builds a module graph from import relationships."""
        for root, _, files in os.walk(repo_path):
            for file in files:
                if file.endswith(('.py', '.js', '.ts')):
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, repo_path).replace('\\', '/')
                    
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
                        resolved = self.resolve_import(imp, repo_path, file_path)
                        if resolved:
                            # Normalize path for graph consistency
                            resolved = resolved.replace('\\', '/')
                            self.storage.add_edge(EdgeBase(
                                source=rel_path.replace('\\', '/'),
                                target=resolved,
                                type=EdgeType.IMPORTS
                            ))

    def get_pagerank(self) -> Dict[str, float]:
        if not self.storage.graph.nodes:
            return {}
        try:
            return nx.pagerank(self.storage.graph)
        except Exception:
            return {}

    def analyze_git_velocity(self, repo_path: str) -> Dict[str, int]:
        velocity = {}
        try:
            # Get changes in the last 30 days
            result = subprocess.run(
                ["git", "log", "--since='30 days ago'", "--name-only", "--pretty=format:"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            for line in result.stdout.splitlines():
                if line.strip():
                    file = line.strip()
                    velocity[file] = velocity.get(file, 0) + 1
        except Exception:
            pass
        return velocity

    def detect_dead_code_candidates(self) -> List[str]:
        """Nodes with zero in-degree are potential dead code."""
        candidates = [
            n for n, d in self.storage.graph.in_degree() 
            if d == 0 and self.storage.graph.nodes[n].get('type') == NodeType.FILE
        ]
        return candidates

    def run_analysis(self, repo_path: str) -> Dict[str, Any]:
        self.survey_repository(repo_path)
        
        # Calculate metrics
        pr = self.get_pagerank()
        vel = self.analyze_git_velocity(repo_path)
        dead_candidates = self.detect_dead_code_candidates()
        
        # Attach metrics back to the graph nodes
        for node_id in self.storage.graph.nodes:
            self.storage.graph.nodes[node_id]['pagerank'] = pr.get(node_id, 0.0)
            self.storage.graph.nodes[node_id]['change_velocity_30d'] = float(vel.get(node_id, 0))
            self.storage.graph.nodes[node_id]['is_dead_code_candidate'] = node_id in dead_candidates

        return {
            "pagerank": pr,
            "velocity": vel,
            "dead_code": dead_candidates
        }
