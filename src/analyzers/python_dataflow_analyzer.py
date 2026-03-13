import ast
from typing import Any, Dict, List, Optional, Tuple


class PythonDataflowAnalyzer(ast.NodeVisitor):
    """
    Lightweight, static Python dataflow detector for lineage:
    - pandas: read_* and to_sql
    - pyspark: spark.read.*, DataFrame.write.*
    - sqlalchemy: engine.execute / session.execute with SQL strings

    It intentionally over-approximates and logs dynamic/unresolved cases.
    """

    def __init__(self) -> None:
        self.reads: List[Dict[str, Any]] = []
        self.writes: List[Dict[str, Any]] = []

    def analyze(self, source: str, filename: str = "<unknown>") -> Dict[str, Any]:
        try:
            tree = ast.parse(source, filename=filename)
        except SyntaxError as e:
            return {"error": str(e), "reads": [], "writes": []}

        self.reads = []
        self.writes = []
        self.visit(tree)
        return {"reads": self.reads, "writes": self.writes}

    # Helpers

    def _extract_table_from_call(self, node: ast.Call) -> Tuple[Optional[str], bool]:
        """
        Return (table_name, is_dynamic) where table_name may be None if unresolved.
        """
        # Prefer first positional arg if it is a literal string
        if node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return arg.value, False
        # Fallback: dynamic or complex expression
        return None, True

    def _record_io(
        self,
        kind: str,
        node: ast.Call,
        engine: str,
        operation: str,
    ) -> None:
        table, is_dynamic = self._extract_table_from_call(node)
        entry = {
            "kind": kind,
            "engine": engine,
            "operation": operation,
            "table": table,
            "is_dynamic": is_dynamic,
            "lineno": getattr(node, "lineno", None),
            "end_lineno": getattr(node, "end_lineno", None),
        }
        if kind == "read":
            self.reads.append(entry)
        else:
            self.writes.append(entry)

    # Visitor

    def visit_Call(self, node: ast.Call) -> Any:
        # Detect attribute-style calls like df.to_sql, spark.read.table, df.write.parquet, etc.
        func = node.func

        # pandas: pd.read_* and DataFrame.to_sql
        if isinstance(func, ast.Attribute):
            attr_name = func.attr

            # pandas read
            if attr_name.startswith("read_"):
                # pd.read_csv / pd.read_sql / pd.read_parquet ...
                self._record_io("read", node, engine="pandas", operation=attr_name)

            # pandas write to SQL
            if attr_name == "to_sql":
                self._record_io("write", node, engine="pandas", operation="to_sql")

            # pyspark: spark.read.* and df.write.*
            # spark.read.table / spark.read.parquet
            if isinstance(func.value, ast.Attribute):
                owner = func.value
                if isinstance(owner.value, ast.Name):
                    base_name = owner.value.id
                    # spark.read.*
                    if base_name == "spark" and owner.attr == "read":
                        self._record_io("read", node, engine="pyspark", operation=attr_name)

                # df.write.*
                if owner.attr == "write":
                    self._record_io("write", node, engine="pyspark", operation=attr_name)

        # sqlalchemy-ish execute: engine.execute(sql) / session.execute(sql)
        if isinstance(func, ast.Attribute) and func.attr == "execute":
            self._record_io("read", node, engine="sqlalchemy", operation="execute")

        self.generic_visit(node)

