from typing import Any, Dict, List, Tuple
from app.planner.compiler import record_sort_column
from app.planner.plan_schema import AdHocMetric, Plan, Filter
from app.semantic.model import SemanticLayer

# Past this many distinct values a numeric measure stops being a usable grouping:
# every value becomes its own "segment" and the chart is a list of numbers.
MAX_GROUPING_VALUES = 50

def validate_plan(plan: Plan, semantic: SemanticLayer) -> Tuple[Plan, List[str], List[str]]:
    """
    Validates a Plan against the Semantic Layer.
    Returns (healed_plan, errors, assumptions).
    """
    errors: List[str] = []
    assumptions: List[str] = []

    # 1. Normalize metric
    metric_names = {m.name: m for m in semantic.metrics}
    metric_obj = None

    if isinstance(plan.metric, str):
        m_name = plan.metric.lower().strip()
        if m_name in metric_names:
            plan.metric = m_name
            metric_obj = metric_names[m_name]
        else:
            # Try fuzzy match on metric synonyms
            found = False
            for m in semantic.metrics:
                if m_name in [s.lower() for s in m.synonyms]:
                    plan.metric = m.name
                    metric_obj = m
                    assumptions.append(f"'{m_name}' interpreted as metric '{m.name}'")
                    found = True
                    break
            if not found:
                available = ", ".join(m.name for m in semantic.metrics) or "none"
                errors.append(
                    f"UNKNOWN_METRIC: Metric '{plan.metric}' is not registered. "
                    f"Available metrics: {available}."
                )
    elif isinstance(plan.metric, AdHocMetric):
        # The compiler quotes this column into SQL, so it must be one the schema has.
        ad_tbl, _, ad_col = plan.metric.column.partition(".")
        if not (ad_tbl in semantic.tables and ad_col in semantic.tables[ad_tbl].columns):
            errors.append(f"UNKNOWN_COLUMN: Metric column '{plan.metric.column}' not found in the dataset.")
    elif plan.metric is None and plan.intent not in ["dashboard", "detail"]:
        # 'revenue' when the dataset has it, otherwise its first metric.
        default = metric_names.get("revenue") or (semantic.metrics[0] if semantic.metrics else None)
        if default:
            plan.metric = default.name
            metric_obj = default
            assumptions.append(f"Defaulted to metric '{default.name}'")
        else:
            errors.append("NO_METRICS: This dataset has no numeric column to measure.")

    # Every query is bounded by a time window, so there must be a date column to use.
    has_time_column = bool(
        (plan.time and plan.time.column)
        or (metric_obj and metric_obj.time_column)
        or semantic.time.primary_column
    )
    if plan.intent not in ["dashboard", "detail"] and metric_obj and not has_time_column:
        errors.append(
            "NO_TIME_COLUMN: This dataset has no date column, so questions that need a "
            "time range cannot be answered."
        )

    # A record-level ranking ("top 10 records by delay_minutes") needs a metric that
    # is one column. When it is not, the listing stays unordered - say so rather than
    # let the rows look ranked.
    if plan.intent == "detail" and plan.sort and plan.sort.by == "metric" and (
        metric_obj is not None or isinstance(plan.metric, AdHocMetric)
    ):
        fact = metric_obj.table if metric_obj else semantic.fact_table
        if fact and record_sort_column(plan, semantic, fact) is None:
            label = metric_obj.name if metric_obj else plan.metric.column  # type: ignore[union-attr]
            assumptions.append(
                f"Records are not ordered: '{label}' is not a single column that can be ranked record by record"
            )

    # 2. Heal Intent Mismatches
    if plan.intent == "kpi" and len(plan.dimensions) > 0:
        plan.intent = "breakdown"
    elif plan.intent == "trend" and (not plan.time or not plan.time.grain):
        if not plan.time:
            from app.planner.plan_schema import TimeSpec
            plan.time = TimeSpec(grain="month")
        else:
            plan.time.grain = "month"
        assumptions.append("Set trend time grain to 'month'")

    if plan.intent == "ranking" and not plan.limit:
        plan.limit = 10

    if plan.intent == "why":
        if metric_obj and not metric_obj.additive:
            errors.append(f"NON_ADDITIVE_WHY: Cannot decompose non-additive metric '{metric_obj.name}'.")
        if not plan.time or not plan.time.range:
            from app.planner.plan_schema import TimeSpec, LastN
            plan.time = TimeSpec(range=LastN(unit="month", n=1))
            assumptions.append("Defaulted 'why' target window to last month")
        if not plan.comparison:
            from app.planner.plan_schema import Comparison
            plan.comparison = Comparison(type="previous_period")

    # 3. Validate Dimensions & Reachability
    valid_dims = []
    for dim in plan.dimensions:
        if "." not in dim:
            # Try resolving naked column
            found_col = None
            for tname, tmeta in semantic.tables.items():
                if dim in tmeta.columns:
                    found_col = f"{tname}.{dim}"
                    break
            if found_col:
                dim = found_col
            else:
                errors.append(f"UNKNOWN_COLUMN: Dimension '{dim}' not found in any table.")
                continue

        tbl, col = dim.split(".", 1)
        if tbl not in semantic.tables:
            errors.append(f"UNKNOWN_TABLE: Table '{tbl}' does not exist.")
            continue
        if col not in semantic.tables[tbl].columns:
            errors.append(f"UNKNOWN_COLUMN: Column '{col}' does not exist in table '{tbl}'.")
            continue

        valid_dims.append(f"{tbl}.{col}")

    plan.dimensions = valid_dims

    # 3b. A numeric measure with many distinct values is not a grouping key. This is
    # what turns "top 10 delay_minutes by weight" into a chart of delay values as
    # categories: the plan is well-formed, so nothing downstream can tell it is wrong.
    if plan.intent in ("breakdown", "ranking", "trend", "compare"):
        for dim in valid_dims:
            d_tbl, d_col = dim.split(".", 1)
            col_meta = semantic.tables[d_tbl].columns[d_col]
            # Judged by the column's type as well as its role, so a dataset stored
            # before the tagger learned to call whole-number columns measures (role
            # "text") is still protected. A numeric ID stays groupable.
            numeric_measure = col_meta.role in ("measure", "text") and col_meta.dtype in ("BIGINT", "DOUBLE")
            if numeric_measure and col_meta.distinct > MAX_GROUPING_VALUES:
                categories = [
                    c.display_name
                    for t in semantic.tables.values()
                    for c in t.columns.values()
                    if c.role == "dimension"
                ][:3]
                hint = f" Group by a category instead, such as {', '.join(categories)}." if categories else ""
                errors.append(
                    f"MEASURE_AS_DIMENSION: '{col_meta.display_name}' is a numeric measure with "
                    f"{col_meta.distinct} distinct values, so results cannot be grouped by it (every value "
                    f"would become its own segment). To see the individual records with the highest or "
                    f"lowest '{col_meta.display_name}', ask for the top or bottom N records by it.{hint}"
                )

    # 4. Validate Filters
    valid_filters = []
    for f in plan.filters:
        col = f.column
        if "." not in col:
            for tname, tmeta in semantic.tables.items():
                if col in tmeta.columns:
                    col = f"{tname}.{col}"
                    break
        tbl, cname = col.split(".", 1)
        if tbl in semantic.tables and cname in semantic.tables[tbl].columns:
            valid_filters.append(Filter(column=col, op=f.op, value=f.value))
        else:
            errors.append(f"UNKNOWN_FILTER_COLUMN: Column '{col}' not found.")

    plan.filters = valid_filters
    return plan, errors, assumptions
