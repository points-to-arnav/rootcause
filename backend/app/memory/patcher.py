import copy
from typing import Any, Dict, Optional
from app.planner.plan_schema import Plan

def patch_plan(current_plan_dict: Optional[Dict[str, Any]], changes: Dict[str, Any]) -> Plan:
    """
    Deterministically merges a partial plan 'changes' into 'current_plan_dict'.
    Follows rules from conversation-memory.md.
    """
    merged = copy.deepcopy(current_plan_dict) if current_plan_dict else {}

    # 1. Top-level fields
    for field in ["intent", "metric", "dimensions", "comparison", "sort", "limit"]:
        if field in changes:
            if changes[field] is None:
                if field == "dimensions":
                    merged["dimensions"] = []
                else:
                    merged[field] = None
            else:
                merged[field] = changes[field]

    # 2. Deep merge time
    if "time" in changes:
        if changes["time"] is None:
            merged["time"] = None
        else:
            if "time" not in merged or not merged["time"]:
                merged["time"] = {}
            for t_key, t_val in changes["time"].items():
                if t_val is None:
                    merged["time"].pop(t_key, None)
                else:
                    merged["time"][t_key] = t_val

    # 3. Deep merge why
    if "why" in changes:
        if changes["why"] is None:
            merged["why"] = None
        else:
            if "why" not in merged or not merged["why"]:
                merged["why"] = {}
            for w_key, w_val in changes["why"].items():
                if w_val is None:
                    merged["why"].pop(w_key, None)
                else:
                    merged["why"][w_key] = w_val

    # 4. Filters handling
    filters_list = merged.get("filters", [])

    # filters_remove: list of columns to remove
    if "filters_remove" in changes and isinstance(changes["filters_remove"], list):
        remove_cols = set(changes["filters_remove"])
        filters_list = [f for f in filters_list if f.get("column") not in remove_cols]

    # filters_add: append or replace same column+op
    if "filters_add" in changes and isinstance(changes["filters_add"], list):
        for new_f in changes["filters_add"]:
            # remove existing with same column and op
            filters_list = [f for f in filters_list if not (f.get("column") == new_f.get("column") and f.get("op") == new_f.get("op"))]
            filters_list.append(new_f)

    # full filters replacement if passed directly
    if "filters" in changes and isinstance(changes["filters"], list):
        filters_list = changes["filters"]

    merged["filters"] = filters_list

    # 5. Intent sanitization
    new_intent = merged.get("intent", "kpi")
    if new_intent == "kpi":
        merged["dimensions"] = []
        merged["limit"] = None
    elif new_intent == "ranking" and not merged.get("limit"):
        merged["limit"] = 10

    return Plan.model_validate(merged)
