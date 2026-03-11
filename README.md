# The Brownfield Cartographer

The Brownfield Cartographer is a specialized tool designed to map and analyze complex, legacy codebases. It focuses on structural analysis and data lineage to provide insights into module relationships, code health, and data flow.



This repository contains the core infrastructure 

### 1. Knowledge Graph Data Models & Storage Layer
- **Pydantic Schemas**: Located in `src/models/graph_models.py`, defining typed `NodeBase`, `EdgeBase`, and `KnowledgeGraphData`.
- **Storage Layer**: Located in `src/graph/storage.py`, providing a `GraphStorage` wrapper for NetworkX with JSON serialization/deserialization.

### 2. Multi-Language AST Parsing
- **Analyzer**: `src/analyzers/tree_sitter_analyzer.py` utilizes `tree-sitter` to parse multiple languages (Python, JS, etc.) and extract structural elements like imports, function definitions, and class definitions.

### 3. SQL Dependency Extraction
- **SQL Analyzer**: `src/analyzers/sql_analyzer.py` uses `sqlglot` to extract table-level dependencies (sources and targets) with multi-dialect support.

### 4. Surveyor Agent
- **Capabilities**: Located in `src/agents/surveyor.py`. It constructs module graphs, calculates PageRank for component importance, analyzes Git velocity for hotspots, and identifies potential dead code.

### 5. Hydrologist Agent
- **Capabilities**: Located in `src/agents/hydrologist.py`. It builds unified data lineage DAGs and supports impact analysis queries such as `blast_radius`, `find_sources`, and `find_sinks`.

### 6. Pipeline Orchestration & CLI
- **Entry Point**: `src/cli.py` provides a command-line interface to point the tool at a repository, sequence the agents, and serialize results to an output directory.

## Usage

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run analysis:
   ```bash
   python -m src.cli /path/to/your/repo
   ```
