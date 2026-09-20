import re
from typing import Any, Dict
from app.semantic.model import ColumnMeta, ColumnRole

ID_PATTERN = re.compile(r"(^|_)(id|key|code|no|number)$", re.IGNORECASE)
MEASURE_PATTERN = re.compile(
    r"(amount|price|cost|revenue|sales|total|qty|quantity|units|stock|discount|profit|margin|balance|value|fee|tax|refund)",
    re.IGNORECASE
)
NON_ENTITY_PATTERN = re.compile(
    r"(comment|description|notes?|remarks?|address|url|email|phone)",
    re.IGNORECASE
)

def tag_column(col_name: str, display_name: str, profile: Dict[str, Any], table_row_count: int) -> ColumnMeta:
    """
    Evaluates role tagging rules in priority order:
    time -> id -> measure -> dimension -> text (with entity flag).
    """
    dtype = profile["dtype"]
    distinct = profile["distinct"]
    distinct_ratio = profile["distinct_ratio"]
    null_pct = profile["null_pct"]

    role: ColumnRole = "text"
    is_entity = False

    # 1. Time
    if dtype in ["DATE", "TIMESTAMP"]:
        role = "time"

    # 2. ID
    elif (ID_PATTERN.search(col_name) and distinct_ratio >= 0.40) or (distinct == table_row_count and table_row_count > 1):
        role = "id"

    # 3. Measure
    elif dtype in ["BIGINT", "DOUBLE"] and (MEASURE_PATTERN.search(col_name) or distinct_ratio > 0.05):
        role = "measure"

    # 4. Dimension
    elif dtype in ["BOOLEAN"] or (dtype == "VARCHAR" and distinct <= max(50, int(0.05 * table_row_count))):
        role = "dimension"
    elif dtype in ["BIGINT"] and distinct <= 20 and not MEASURE_PATTERN.search(col_name):
        role = "dimension"

    # 5. Text / Entity
    else:
        role = "text"
        if distinct_ratio >= 0.85 and not NON_ENTITY_PATTERN.search(col_name):
            is_entity = True

    return ColumnMeta(
        name=col_name,
        display_name=display_name,
        dtype=dtype,
        role=role,
        entity=is_entity,
        null_pct=null_pct,
        distinct=distinct,
        min=profile.get("min"),
        max=profile.get("max"),
        samples=profile.get("samples", [])
    )
