import unittest
import os
import shutil
import tempfile
from src.agents.surveyor import SurveyorAgent

class TestSurveyorAgent(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.agent = SurveyorAgent()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_resolve_import_absolute(self):
        # Setup: base_dir/pkg/mod.py
        pkg_dir = os.path.join(self.test_dir, "pkg")
        os.makedirs(pkg_dir)
        mod_file = os.path.join(pkg_dir, "mod.py")
        with open(mod_file, "w") as f:
            f.write("pass")
            
        # Test
        resolved = self.agent.resolve_import("pkg.mod", self.test_dir, os.path.join(self.test_dir, "main.py"))
        self.assertEqual(resolved.replace("\\", "/"), "pkg/mod.py")

    def test_resolve_import_relative_single_dot(self):
        # Setup: base_dir/pkg/a.py, base_dir/pkg/b.py
        # a.py imports .b
        pkg_dir = os.path.join(self.test_dir, "pkg")
        os.makedirs(pkg_dir)
        file_a = os.path.join(pkg_dir, "a.py")
        file_b = os.path.join(pkg_dir, "b.py")
        with open(file_b, "w") as f: f.write("pass")
        
        resolved = self.agent.resolve_import(".b", self.test_dir, file_a)
        self.assertEqual(resolved.replace("\\", "/"), "pkg/b.py")

    def test_resolve_import_relative_triple_dot(self):
        # Setup: base_dir/core.py, base_dir/pkg/sub/a.py
        # a.py imports ...core (grandparent)
        pkg_dir = os.path.join(self.test_dir, "pkg", "sub")
        os.makedirs(pkg_dir)
        file_core = os.path.join(self.test_dir, "core.py")
        file_a = os.path.join(pkg_dir, "a.py")
        with open(file_core, "w") as f: f.write("pass")
        
        resolved = self.agent.resolve_import("...core", self.test_dir, file_a)
        self.assertEqual(resolved.replace("\\", "/"), "core.py")

    def test_detect_circular_dependencies_and_flags(self):
        # Manually build a cycle in the storage graph
        from src.models.graph_models import NodeBase, EdgeBase, NodeType, EdgeType
        
        self.agent.storage.add_node(NodeBase(id="a.py", type=NodeType.FILE, name="a"))
        self.agent.storage.add_node(NodeBase(id="b.py", type=NodeType.FILE, name="b"))
        
        self.agent.storage.add_edge(EdgeBase(source="a.py", target="b.py", type=EdgeType.IMPORTS))
        self.agent.storage.add_edge(EdgeBase(source="b.py", target="a.py", type=EdgeType.IMPORTS))
        
        # Run analysis to trigger flagging
        results = self.agent.run_analysis(self.test_dir)
        
        cycles = results["circular_dependencies"]
        self.assertEqual(len(cycles), 1)
        self.assertIn("a.py", cycles[0])
        
        # Check if nodes are flagged in the graph
        self.assertTrue(self.agent.storage.graph.nodes["a.py"].get("has_circular_dependency"))
        self.assertTrue(self.agent.storage.graph.nodes["b.py"].get("has_circular_dependency"))


if __name__ == "__main__":
    unittest.main()
