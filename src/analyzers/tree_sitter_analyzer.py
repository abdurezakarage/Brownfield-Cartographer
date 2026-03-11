import os
from typing import Dict, List, Any
try:
    import tree_sitter_languages
    from tree_sitter import Parser, Language
except ImportError:
    # Fallback or placeholder for the environment
    tree_sitter_languages = None

class TreeSitterAnalyzer:
    def __init__(self):
        self.languages = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".java": "java",
            ".go": "go",
            ".cpp": "cpp",
            ".c": "c"
        }
        self.parsers = {}
        if tree_sitter_languages:
            for ext, lang_name in self.languages.items():
                try:
                    # Try using tree_sitter_languages first (modern/bundled way)
                    self.parsers[lang_name] = tree_sitter_languages.get_parser(lang_name)
                except Exception:
                    # Fallback: Try importing tree_sitter_[lang] directly (new tree-sitter style)
                    try:
                        import importlib
                        lang_mod = importlib.import_module(f"tree_sitter_{lang_name}")
                        from tree_sitter import Language, Parser
                        lang_obj = Language(lang_mod.language())
                        parser = Parser(lang_obj)
                        self.parsers[lang_name] = parser
                    except Exception as e:
                        print(f"Warning: Could not load parser for {lang_name}: {e}")


    def parse_file(self, file_path: str) -> Dict[str, Any]:
        ext = os.path.splitext(file_path)[1].lower()
        lang_name = self.languages.get(ext)
        parser = self.parsers.get(lang_name) if lang_name else None
        
        if not parser:
            return {"error": f"No parser for {ext}"}

        with open(file_path, "rb") as f:
            content = f.read()

        tree = parser.parse(content)
        return self._analyze_tree(tree, content, lang_name)

    def _analyze_tree(self, tree, content: bytes, lang: str) -> Dict[str, Any]:
        results = {
            "imports": [],
            "functions": [],
            "classes": []
        }
      
        if lang == "python":
            try:
                # Use Query for high-depth extraction
                query_str = """
                (import_from_statement) @import
                (import_statement) @import
                (function_definition 
                    name: (identifier) @func_name
                    parameters: (parameters) @func_params) @func_def
                (class_definition 
                    name: (identifier) @class_name
                    superclasses: (argument_list (identifier) @base_class)? ) @class_def
                """
                query = self.parsers[lang].language.query(query_str)
                captures = query.captures(tree.root_node)
                
                # Process captures to build structured results
                # (Simplification: we still use the walker for now but can extend this)
            except Exception as e:
                print(f"Query error: {e}")
            
        # Fallback/Primary extraction via traversal
        cursor = tree.walk()
        self._traverse(cursor, content, results)
        return results

    def _traverse(self, cursor, content, results):
        node = cursor.node
        if node.type in ["import_from_statement", "import_statement"]:
            results["imports"].append(content[node.start_byte:node.end_byte].decode("utf-8"))
        elif node.type == "function_definition":
            func_data = {"name": None, "decorators": [], "parameters": []}
            for child in node.children:
                if child.type == "identifier":
                    func_data["name"] = content[child.start_byte:child.end_byte].decode("utf-8")
                elif child.type == "parameters":
                    func_data["parameters"] = content[child.start_byte:child.end_byte].decode("utf-8")
                elif child.type == "decorator":
                    func_data["decorators"].append(content[child.start_byte:child.end_byte].decode("utf-8"))
            results["functions"].append(func_data)
        elif node.type == "class_definition":
            class_data = {"name": None, "bases": [], "decorators": []}
            for child in node.children:
                if child.type == "identifier":
                    class_data["name"] = content[child.start_byte:child.end_byte].decode("utf-8")
                elif child.type == "argument_list": # Bases in Python are in the argument list
                    class_data["bases"] = [content[c.start_byte:c.end_byte].decode("utf-8") for c in child.children if c.type == "identifier"]
                elif child.type == "decorator":
                    class_data["decorators"].append(content[child.start_byte:child.end_byte].decode("utf-8"))
            results["classes"].append(class_data)

        if cursor.goto_first_child():
            self._traverse(cursor, content, results)
            while cursor.goto_next_sibling():
                self._traverse(cursor, content, results)
            cursor.goto_parent()
