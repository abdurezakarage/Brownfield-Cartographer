import sqlglot
from sqlglot import exp
from typing import Set, Dict, List, Any

class SQLAnalyzer:
    def __init__(self, default_dialect: str = "postgres"):
        self.default_dialect = default_dialect

    def analyze_query(self, sql_content: str, dialect: str = None) -> Dict[str, Any]:
        dialect = dialect or self.default_dialect
        dependencies = {
            "sources": set(),
            "targets": set(),
            "ctes": set()
        }
        
        try:
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
            return {"error": str(e), "sources": [], "targets": []}

        return {
            "sources": list(dependencies["sources"]),
            "targets": list(dependencies["targets"]),
            "dialect": dialect
        }

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r") as f:
            content = f.read()
        return self.analyze_query(content)
