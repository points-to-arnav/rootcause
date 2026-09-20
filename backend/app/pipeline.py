import os
from typing import Any, Dict, List, Optional
from app.config import settings
from app.memory.patcher import patch_plan
from app.memory.session import SessionState, Turn, save_session
from app.narrator.narrator import narrate_result
from app.planner.compiler import compile_plan_to_sql
from app.planner.executor import execute_query
from app.planner.plan_schema import Plan, PlannerOutput
from app.planner.planner import plan_query
from app.planner.timeutil import resolve_comparison_window, resolve_time_window
from app.planner.validator import validate_plan
from app.semantic.model import SemanticLayer
from app.semantic.value_index import ValueIndex
from app.viz.selector import select_chart
from app.analysis.why_engine import run_why_analysis

def generate_suggestions_by_intent(plan: Plan) -> List[str]:
    """Generates intelligent follow-up suggestions for the user."""
    intent = plan.intent
    if intent == "kpi":
        return ["Show monthly trend for 2026", "Breakdown by region", "Compare with previous month"]
    elif intent == "trend":
        return ["Breakdown by product category", "Show only the last 6 months", "Why did revenue fall last month?"]
    elif intent == "breakdown":
        return ["Only the last six months", "Compare it with previous period", "Drill into the top category"]
    elif intent == "ranking":
        return ["Show top 5 only", "Show monthly trend for top product", "Compare with previous period"]
    elif intent == "compare":
        return ["Which region contributed most to the decline?", "Show the five products with largest decline", "Why did it fall?"]
    elif intent == "why":
        return ["Was it mainly a particular product category?", "Show me the five products responsible for the largest decline", "Show inventory stock levels"]
    return ["Show total revenue", "Create management dashboard", "Top 10 products"]

def match_dq_warnings(plan: Plan, semantic: SemanticLayer) -> List[Dict[str, Any]]:
    """Attaches data quality issues affecting columns or tables used in the plan."""
    used_tables = set()
    used_cols = set()

    for dim in plan.dimensions:
        if "." in dim:
            t, c = dim.split(".", 1)
            used_tables.add(t)
            used_cols.add(f"{t}.{c}")

    for f in plan.filters:
        if "." in f.column:
            t, c = f.column.split(".", 1)
            used_tables.add(t)
            used_cols.add(f"{t}.{c}")

    warnings = []
    for issue in semantic.quality_issues:
        iss_tbl = issue.get("table")
        iss_col = issue.get("column")
        if iss_col and f"{iss_tbl}.{iss_col}" in used_cols:
            warnings.append(issue)
        elif not iss_col and iss_tbl in used_tables:
            warnings.append(issue)

    return warnings[:3]

import logging

logger = logging.getLogger(__name__)

# Fast in-memory cache for demo queries & offline Wi-Fi protection
_DEMO_QUERY_CACHE: Dict[str, Dict[str, Any]] = {}

def run_ask_pipeline(
    session: SessionState,
    semantic: SemanticLayer,
    question: str,
    value_index: Optional[ValueIndex] = None
) -> Dict[str, Any]:
    """
    Executes the full AskData request lifecycle for a single turn.
    Returns standard AskResponse dictionary.
    """
    db_path = os.path.join(settings.DATA_DIR, session.dataset_id, "data.duckdb")

    norm_q = question.strip().lower()
    cache_key = f"{session.dataset_id}:{norm_q}"

    # Fast-path cache hit for instant demo responses (<50ms)
    if cache_key in _DEMO_QUERY_CACHE:
        cached_resp = dict(_DEMO_QUERY_CACHE[cache_key])
        session.history.append(Turn(
            turn=len(session.history) + 1,
            question=question,
            plan=cached_resp.get("plan"),
            summary=(cached_resp.get("narrative") or "")[:100]
        ))
        save_session(session)
        logger.info(f"Serving cached demo query response for: '{question}'")
        return cached_resp

    # 1. LLM Planning with network-resilient heuristic fallback
    current_plan_dict = session.current_plan
    try:
        planner_out: PlannerOutput = plan_query(
            question=question,
            semantic=semantic,
            value_index=value_index,
            current_plan=current_plan_dict,
            recent_turns=[{"question": t.question, "summary": t.summary} for t in session.history[-3:]],
            last_result_head=session.last_result_head
        )
    except Exception as e:
        logger.warning(f"LLM planner call failed ({e}). Falling back to heuristic rule planner.")
        # Determine anchor year dynamically
        from app.planner.timeutil import parse_iso_date
        ayear = "2026"
        if semantic.time.anchor_date:
            try:
                ayear = str(parse_iso_date(semantic.time.anchor_date).year)
            except Exception:
                pass
        p_metric = semantic.metrics[0].name if semantic.metrics else "revenue"

        # Heuristic intent mapping
        if any(w in norm_q for w in ["why", "drop", "fall", "decline", "cause", "reason"]):
            f_plan = Plan(
                intent="why",
                metric=p_metric,
                time=TimeSpec(range=LastN(unit="month", n=1)),
                comparison=Comparison(type="previous_period")
            )
        elif any(w in norm_q for w in ["month", "trend", "year", "2024", "2025", "2026", "history", "progression"]):
            f_plan = Plan(
                intent="trend",
                metric=p_metric,
                time=TimeSpec(range=Calendar(unit="year", value=ayear), grain="month")
            )
        elif any(w in norm_q for w in ["region", "category", "breakdown", "by ", "split"]):
            # Pick first available dimension
            first_dim = None
            for tname, tmeta in semantic.tables.items():
                for cname, cmeta in tmeta.columns.items():
                    if cmeta.role == "dimension":
                        first_dim = f"{tname}.{cname}"
                        break
                if first_dim:
                    break
            f_plan = Plan(intent="breakdown", metric=p_metric, dimensions=[first_dim] if first_dim else [])
        elif any(w in norm_q for w in ["top", "rank", "best", "worst"]):
            first_dim = None
            for tname, tmeta in semantic.tables.items():
                for cname, cmeta in tmeta.columns.items():
                    if cmeta.entity or cmeta.distinct > 10:
                        first_dim = f"{tname}.{cname}"
                        break
                if first_dim:
                    break
            f_plan = Plan(intent="ranking", metric=p_metric, dimensions=[first_dim] if first_dim else [], limit=10)
        else:
            f_plan = Plan(intent="kpi", metric=p_metric)

        planner_out = PlannerOutput(
            status="ok",
            is_follow_up=False,
            plan=f_plan,
            assumptions=["Heuristic fallback query plan applied due to LLM network/provider unavailability."]
        )

    if planner_out.status != "ok":
        return {
            "status": planner_out.status,
            "message": planner_out.message or "I need more information to answer your question.",
            "plan": None,
            "assumptions": planner_out.assumptions,
            "resolved_time": None,
            "sql": None,
            "result": None,
            "chart": None,
            "narrative": planner_out.message or "Unsupported question.",
            "dq_warnings": [],
            "why": None,
            "suggestions": ["Show total revenue", "Monthly revenue for 2026", "Create management dashboard"],
            "mode": "plan"
        }

    # 2. Follow-up Patch or New Plan
    if planner_out.is_follow_up and planner_out.changes and current_plan_dict:
        plan = patch_plan(current_plan_dict, planner_out.changes)
    else:
        plan = planner_out.plan or Plan(intent="kpi", metric="revenue")

    # Heal intent if question clearly indicates a "why" root cause inquiry
    q_lower = question.lower()
    why_keywords = ["why did", "why has", "why is", "why was", "why were", "what caused", "explain drop", "explain fall", "explain decline", "reason for drop", "reason for fall", "why"]
    if any(kw in q_lower for kw in why_keywords) and plan.intent != "why":
        plan.intent = "why"

    # 3. Validate Plan
    plan, errors, val_assumptions = validate_plan(plan, semantic)
    all_assumptions = planner_out.assumptions + val_assumptions

    if errors:
        return {
            "status": "error",
            "message": "Plan validation failed: " + "; ".join(errors),
            "plan": plan.model_dump(),
            "assumptions": all_assumptions,
            "resolved_time": None,
            "sql": None,
            "result": None,
            "chart": None,
            "narrative": "Unable to execute query due to schema constraints.",
            "dq_warnings": [],
            "why": None,
            "suggestions": ["Show total revenue", "Revenue by region"],
            "mode": "plan"
        }

    # 4. Resolve Time
    anchor_str = semantic.time.anchor_date or "2026-08-31"
    t_start, t_end, cur_label = resolve_time_window(
        plan.time.range if plan.time else None,
        anchor_str=anchor_str,
        min_date_str=semantic.time.min
    )

    baseline_label = None
    baseline_window = None
    if plan.comparison:
        b_start, b_end, baseline_label = resolve_comparison_window(t_start, t_end, plan.comparison.type)
        baseline_window = (b_start, b_end)

    resolved_time = {
        "start": str(t_start),
        "end": str(t_end),
        "label": cur_label,
        "baseline": {
            "start": str(baseline_window[0]),
            "end": str(baseline_window[1]),
            "label": baseline_label
        } if baseline_window else None
    }

    # 5. Route Execution
    why_result = None

    if plan.intent == "why":
        # Execute Why Engine
        metric_name = plan.metric if isinstance(plan.metric, str) else "revenue"
        candidate_dims = plan.why.dimensions if plan.why and plan.why.dimensions else None
        max_d = plan.why.max_depth if plan.why else 3

        why_result = run_why_analysis(
            db_path=db_path,
            semantic=semantic,
            metric_name=metric_name,
            target_window=(t_start, t_end),
            baseline_window=baseline_window or (t_start, t_end),
            base_filters=plan.filters,
            candidate_dims=candidate_dims,
            max_depth=max_d
        )

        # Build table for Why result
        columns = ["Segment", "Delta", "Contribution", "Lift"]
        rows = []
        if why_result.get("dimensions"):
            top_dim = why_result["dimensions"][0]
            for s in top_dim.get("segments", []):
                rows.append([s["value"], s["delta"], f"{round(s['contribution']*100, 1)}%", s["lift"]])

        result = {
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": False
        }
        sql = "-- Executed Why Decomposition Engine in Python/DuckDB"

    else:
        # Standard Plan -> SQL Compiler -> Executor
        sql, params = compile_plan_to_sql(plan, semantic, (t_start, t_end), baseline_window)
        result = execute_query(db_path, sql, params)

    # 6. Chart Selection
    metric_format = "currency"
    if isinstance(plan.metric, str):
        m_obj = next((m for m in semantic.metrics if m.name == plan.metric), None)
        if m_obj:
            metric_format = m_obj.format

    chart = select_chart(plan, result, metric_format)

    # 7. Data Quality Warnings
    dq_warnings = match_dq_warnings(plan, semantic)

    # 8. Narrator
    narrative = narrate_result(
        question=question,
        plan=plan,
        result=result,
        period_label=cur_label,
        baseline_label=baseline_label,
        dq_warnings=dq_warnings,
        why_result=why_result
    )

    suggestions = generate_suggestions_by_intent(plan)

    # 9. Update & Persist Session
    session.current_plan = plan.model_dump()
    if result.get("rows"):
        session.last_result_head = {
            "columns": result.get("columns", [])[:5],
            "rows": result.get("rows", [])[:5]
        }
    session.history.append(Turn(
        turn=len(session.history) + 1,
        question=question,
        plan=plan.model_dump(),
        summary=narrative[:100]
    ))
    save_session(session)

    resp = {
        "status": "ok",
        "message": None,
        "plan": plan.model_dump(),
        "assumptions": all_assumptions,
        "resolved_time": resolved_time,
        "sql": sql,
        "result": result,
        "chart": chart,
        "narrative": narrative,
        "dq_warnings": dq_warnings,
        "why": why_result,
        "suggestions": suggestions,
        "mode": "plan"
    }
    _DEMO_QUERY_CACHE[cache_key] = resp
    return resp

