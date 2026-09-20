from typing import Any, Dict, List, Tuple
from app.planner.plan_schema import Plan, Filter
from app.semantic.model import SemanticLayer

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
                errors.append(f"UNKNOWN_METRIC: Metric '{plan.metric}' is not registered.")
    elif plan.metric is None and plan.intent not in ["dashboard", "detail"]:
        # Default to primary metric 'revenue' if available
        if "revenue" in metric_names:
            plan.metric = "revenue"
            metric_obj = metric_names["revenue"]
            assumptions.append("Defaulted to metric 'revenue'")

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
