import re
from typing import Any, Dict
from app.semantic.model import ColumnMeta, ColumnRole

ID_PATTERN = re.compile(r"(^|_)(id|key|code|no|number)$", re.IGNORECASE)
MEASURE_PATTERN = re.compile(
    r"(amount|price|cost|revenue|sales|total|qty|quantity|units|stock|discount|profit|margin|balance|value|fee|tax|refund)"
    # Whole-word only, so `count` does not match `country`.
    r"|(?:^|_)(?:count|rate|pct|percent|ratio|latency|spend|duration|volume|clicks|views|visits|hits)(?:_|$)",
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

    # 2. ID. Being unique in every row is not enough on its own: a small table of
    # amounts or counts is often all-distinct, and calling those IDs leaves the
    # dataset with nothing to measure. A float is never a key, and a column named
    # like a measure (spend, request_count) is a measure whatever its cardinality.
    elif (ID_PATTERN.search(col_name) and distinct_ratio >= 0.40) or (
        distinct == table_row_count
        and table_row_count > 1
        and dtype != "DOUBLE"
        and not MEASURE_PATTERN.search(col_name)
    ):
        role = "id"

    # 3. Measure. A DOUBLE is a measure however few distinct values it has: rates and
    # percentages repeat a lot (0.097, 48.8) yet are still things to aggregate, and a
    # float is almost never a category. Low-cardinality integers stay ambiguous.
    elif dtype == "DOUBLE" or (
        dtype == "BIGINT" and (MEASURE_PATTERN.search(col_name) or distinct_ratio > 0.05)
    ):
        role = "measure"

    # 4. Dimension
    elif dtype in ["BOOLEAN"] or (dtype == "VARCHAR" and distinct <= max(50, int(0.05 * table_row_count))):
        role = "dimension"
    elif dtype in ["BIGINT"] and distinct <= 20 and not MEASURE_PATTERN.search(col_name):
        role = "dimension"

    # A whole-number column that reached here has more than 20 distinct values but
    # under 5% of the rows (delay_minutes: 94 values in 3,306 rows). It is a number
    # somebody will want to rank and total, not free text, and calling it text meant
    # it never became a metric - so a question about it could only be answered by
    # substituting some other measure.
    elif dtype == "BIGINT":
        role = "measure"

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
