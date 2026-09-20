from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict

ColumnRole = Literal["id", "time", "measure", "dimension", "text"]

class ColumnMeta(BaseModel):
    name: str
    display_name: str
    dtype: str
    role: ColumnRole
    entity: bool = False
    description: Optional[str] = None
    null_pct: float = 0.0
    distinct: int = 0
    min: Optional[str] = None
    max: Optional[str] = None
    samples: List[Any] = []
    source: str = "auto"

class TableMeta(BaseModel):
    name: str
    display_name: str
    row_count: int
    role: Literal["fact", "dimension", "mapping"] = "dimension"
    columns: Dict[str, ColumnMeta]

class Relationship(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    from_col: str = Field(alias="from")
    to_col: str = Field(alias="to")
    type: Literal["many_to_one", "one_to_one"] = "many_to_one"
    confidence: float
    containment: float
    parent_unique: bool
    confirmed: bool = False

class Metric(BaseModel):
    name: str
    label: str
    table: str
    expr: str
    additive: bool = True
    format: Literal["currency", "count", "percent", "number"] = "number"
    time_behavior: Literal["flow", "snapshot"] = "flow"
    time_column: Optional[str] = None
    extra_joins: List[Dict[str, Any]] = []
    synonyms: List[str] = []
    description: Optional[str] = None
    source: str = "auto"

class TimeInfo(BaseModel):
    primary_column: Optional[str] = None
    min: Optional[str] = None
    max: Optional[str] = None
    anchor_date: Optional[str] = None

class SemanticLayer(BaseModel):
    dataset_id: str
    tables: Dict[str, TableMeta]
    relationships: List[Relationship] = []
    metrics: List[Metric] = []
    time: TimeInfo = TimeInfo()
    quality_issues: List[Dict[str, Any]] = []

    @property
    def fact_table(self) -> Optional[str]:
        for tname, tmeta in self.tables.items():
            if tmeta.role == "fact":
                return tname
        return list(self.tables.keys())[0] if self.tables else None

