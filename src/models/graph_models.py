from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class NodeType(str, Enum):
    FILE = "file"
    FUNCTION = "function"
    CLASS = "class"
    MODULE = "module"
    TABLE = "table"
    QUERY = "query"

class NodeBase(BaseModel):
    id: str
    type: NodeType
    name: str
    path: Optional[str] = None
    
    # Analytical Metadata
    change_velocity_30d: float = 0.0
    is_dead_code_candidate: bool = False
    purpose_statement: Optional[str] = None
    domain_cluster: Optional[str] = None
    
    properties: Dict[str, Any] = Field(default_factory=dict)

class EdgeType(str, Enum):
    IMPORTS = "imports"
    CALLS = "calls"
    DEFINES = "defines" # e.g. File defines Class
    DEPENDS_ON = "depends_on"
    READS = "reads"
    WRITES = "writes"

class EdgeBase(BaseModel):
    source: str
    target: str
    type: EdgeType
    properties: Dict[str, Any] = Field(default_factory=dict)

class KnowledgeGraphData(BaseModel):
    nodes: List[NodeBase]
    edges: List[EdgeBase]
