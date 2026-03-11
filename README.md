# The Brownfield Cartographer

The Brownfield Cartographer is a specialized tool designed to map and analyze complex, legacy codebases. It focuses on structural analysis and data lineage to provide insights into module relationships, code health, and data flow.



This repository contains the core infrastructure 

### 1. Knowledge Graph Data Models & Storage Layer
- **Rich Pydantic Schemas**: Defined in `src/models/graph_models.py` with analytical fields: `change_velocity_30d`, `is_dead_code_candidate`, `purpose_statement`, and `domain_cluster`.
- **Advanced Storage Layer**: `src/graph/storage.py` provides a typed NetworkX wrapper with full JSON serialization/deserialization, preserving all analytical metadata.

### 2. Multi-Language AST Parsing
- **Analyzer**: `src/analyzers/tree_sitter_analyzer.py` utilizes `tree-sitter` for high-depth parsing.
- **Python Depth**: Extracts function signatures, class inheritance (base classes), and decorators.
- **YAML Config Parsing**: `src/analyzers/yaml_analyzer.py` extracts pipeline hierarchies and dependencies from configuration files.

### 3. SQL & dbt Dependency Extraction
- **SQL Analyzer**: `src/analyzers/sql_analyzer.py` uses `sqlglot` for robust lineage extraction.
- **dbt Support**: Built-in regex-based pattern recognition for dbt `ref()` and `source()` calls.
- **Target/Source Distinction**: Automatically distinguishes between read and write operations in queries.

### 4. Surveyor Agent (Structural Analysis)
- **Module Graph**: Constructs a complete import graph with automated relative path resolution.
- **Analytical Insights**: Calculates PageRank, 30-day git velocity, and detects dead code candidates/circular dependencies.
- **Enriched Nodes**: Analytical results are attached directly to the graph nodes for downstream use.

### 5. Hydrologist Agent (Data Lineage)
- **Unified Lineage**: Merges Python data flow, SQL dependencies, and YAML pipeline topology into a single DAG.
- **Graph Queries**: Supports `blast_radius` (BFS/DFS traversal), `find_sources`, and `find_sinks`.
- **Edge Metadata**: Edges carry transformation types and source file references.

### 6. Pipeline Orchestration & CLI
- **Automated Workflow**:Sequences Surveyor and Hydrologist with a single command.
- **Remote Support**: CLI accepts GitHub URLs and automatically clones repositories for analysis.
- **Robust Serialization**: Writes both `survey_graph.json` and `lineage_graph.json` to a configurable output directory.

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run analysis:
   ```bash
   python -m src.cli /path/to/your/repo
   ```
