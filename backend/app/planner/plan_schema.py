from datetime import date
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

Intent = Literal["kpi", "trend", "breakdown", "ranking", "compare", "why", "detail", "dashboard"]
Agg = Literal["sum", "avg", "min", "max", "count", "count_distinct"]
Op = Literal["=", "!=", "in", "not_in", ">", ">=", "<", "<=", "between", "contains"]
Unit = Literal["day", "week", "month", "quarter", "year"]
Scalar = Union[str, int, float, bool]

class AdHocMetric(BaseModel):
    agg: Agg
    column: str  # e.g. "sales.amount"

class Filter(BaseModel):
    column: str
    op: Op = "="
    value: Union[Scalar, List[Scalar], None]

class LastN(BaseModel):
    type: Literal["last_n"] = "last_n"
    unit: Unit
    n: int = Field(default=1, ge=1, le=1000)

class Calendar(BaseModel):
    type: Literal["calendar"] = "calendar"
    unit: Literal["month", "quarter", "year"]
    value: str  # e.g. "2026-08", "2026-Q3", "2026"

class Between(BaseModel):
    type: Literal["between"] = "between"
    start: date
    end: date

class AllTime(BaseModel):
    type: Literal["all"] = "all"

TimeRange = Annotated[Union[LastN, Calendar, Between, AllTime], Field(discriminator="type")]

class TimeSpec(BaseModel):
    column: Optional[str] = None
    range: Optional[TimeRange] = None
    grain: Optional[Unit] = None

class Comparison(BaseModel):
    type: Literal["previous_period", "previous_year"] = "previous_period"

class Sort(BaseModel):
    by: Literal["metric", "delta", "dimension", "time"] = "metric"
    dir: Literal["asc", "desc"] = "desc"

class WhySpec(BaseModel):
    dimensions: Optional[List[str]] = None
    max_depth: int = Field(default=3, ge=1, le=4)

class Plan(BaseModel):
    intent: Intent
    metric: Union[str, AdHocMetric, None] = None
    dimensions: List[str] = []
    filters: List[Filter] = []
    time: Optional[TimeSpec] = None
    comparison: Optional[Comparison] = None
    sort: Optional[Sort] = None
    limit: Optional[int] = Field(default=None, ge=1)
    why: Optional[WhySpec] = None

class PlannerOutput(BaseModel):
    status: Literal["ok", "needs_clarification", "unsupported"] = "ok"
    is_follow_up: bool = False
    plan: Optional[Plan] = None
    changes: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    assumptions: List[str] = []
