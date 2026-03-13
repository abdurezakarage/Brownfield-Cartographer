import os
import sqlglot
from sqlglot import exp
from typing import Dict, Any


class SQLAnalyzer:
    """
    SQL lineage extractor backed by sqlglot.
    Supports multiple dialects (postgres + optional bigquery/snowflake/duckdb via filename suffix).
    """

    DIALECT_SUFFIX_MAP = {
        ".bq.sql": "bigquery",
        ".snowflake.sql": "snowflake",
        ".duckdb.sql": "duckdb",
    }

    def __init__(self, default_dialect: str = "postgres"):
        self.default_dialect = default_dialect

    def _infer_dialect_from_path(self, file_path: str) -> str:
        basename = os.path.basename(file_path).lower()
        for suffix, dialect in self.DIALECT_SUFFIX_MAP.items():
            if basename.endswith(suffix):
                return dialect
        return self.default_dialect

    def analyze_query(self, sql_content: str, dialect: str | None = None) -> Dict[str, Any]:
        dialect = dialect or self.default_dialect
        dependencies = {
            "sources": set(),
            "targets": set(),
            "ctes": set(),
        }

        try:
            # Basic dbt pattern matching (since Jinja isn't rendered here)
            import re

            refs = re.findall(r"ref\(['\"](.+?)['\"]\)", sql_content)
            for r in refs:
                dependencies["sources"].add(r.lower())

            sources = re.findall(r"source\(['\"].+?['\"]\s*,\s*['\"](.+?)['\"]\)", sql_content)
            for s in sources:
                dependencies["sources"].add(s.lower())

            expressions = sqlglot.parse(sql_content, read=dialect)
            for expression in expressions:
                # Extract CTEs first so we can exclude them from sources
                for cte in expression.find_all(exp.CTE):
                    dependencies["ctes"].add(cte.alias_or_name.lower())

                # Find all tables used
                for table in expression.find_all(exp.Table):
                    table_name = table.name.lower()

                    # Determine if it's a target (CREATE, INSERT, UPDATE, DELETE)
                    parent = table.parent
                    while parent:
                        if isinstance(parent, (exp.Create, exp.Insert, exp.Update, exp.Delete)):
                            dependencies["targets"].add(table_name)
                            break
                        parent = parent.parent
                    else:
                        # If not a target, it's likely a source
                        dependencies["sources"].add(table_name)

            # Remove CTEs from sources (as they aren't external tables)
            dependencies["sources"] -= dependencies["ctes"]

        except Exception as e:
            # Log and skip gracefully as per rubric
            print(f"Warning: Could not parse SQL: {e}")
            return {"error": str(e), "sources": list(dependencies["sources"]), "targets": [], "dialect": dialect}

        return {
            "sources": list(dependencies["sources"]),
            "targets": list(dependencies["targets"]),
            "dialect": dialect,
        }

    def analyze_file(self, file_path: str, dialect: str | None = None) -> Dict[str, Any]:
        with open(file_path, "r") as f:
            content = f.read()
        dialect = dialect or self._infer_dialect_from_path(file_path)
        return self.analyze_query(content, dialect=dialect)
