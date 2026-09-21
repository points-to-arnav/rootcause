import json
import os
from typing import Any, Dict, List, Optional
from app.config import settings
from app.memory.patcher import patch_plan
from app.memory.session import SessionState, Turn, save_session
from app.narrator.narrator import narrate_result
from app.planner.compiler import compile_plan_to_sql
from app.planner.executor import execute_query
from app.planner.plan_schema import (
    Calendar,
    Comparison,
    LastN,
    Plan,
    PlannerOutput,
    TimeSpec,
)
from app.llm.stats import STATS
from app.planner.planner import plan_query
from app.planner.timeutil import resolve_comparison_window, resolve_time_window
from app.planner.validator import validate_plan
from app.semantic.model import SemanticLayer
from app.semantic.value_index import ValueIndex
from app.viz.chart_request import chart_request_note, parse_chart_request
from app.viz.selector import select_chart
from app.analysis.why_engine import run_why_analysis

def _is_retail(semantic: SemanticLayer) -> bool:
    """The demo wording below (revenue, region, product category) only fits data that has a revenue metric."""
    return any(m.name == "revenue" for m in semantic.metrics)


def _metric_for(plan: Optional[Plan], semantic: SemanticLayer):
    name = plan.metric if plan is not None and isinstance(plan.metric, str) else None
    found = next((m for m in semantic.metrics if m.name == name), None)
    return found or (semantic.metrics[0] if semantic.metrics else None)


def _first_dimension(semantic: SemanticLayer, exclude: Optional[List[str]] = None) -> Optional[str]:
    """A readable name for the first categorical column, fact table first."""
    skip = set(exclude or [])
    fact = semantic.fact_table
    for tname in sorted(semantic.tables, key=lambda t: t != fact):
        for cname, cmeta in semantic.tables[tname].columns.items():
            if cmeta.role == "dimension" and f"{tname}.{cname}" not in skip:
                return cname.replace("_", " ")
    return None


def starter_suggestions(semantic: SemanticLayer) -> List[str]:
    """Questions that are certain to be answerable for this dataset."""
    if _is_retail(semantic):
        return ["Show total revenue", "Revenue by region"]
    metric = _metric_for(None, semantic)
    if metric is None:
        return []
    label = metric.label.lower()
    dim = _first_dimension(semantic)
    questions = [f"What is total {label}?", f"Show {label} by month"]
    if dim:
        questions.append(f"{label.capitalize()} by {dim}")
    return questions


def _generic_suggestions(plan: Plan, semantic: SemanticLayer) -> List[str]:
    metric = _metric_for(plan, semantic)
    if metric is None:
        return []
    label = metric.label.lower()
    dim = _first_dimension(semantic, plan.dimensions)
    by_dim = [f"{label.capitalize()} by {dim}"] if dim else []
    why = [f"Why did {label} change last month?"] if metric.additive else []

    if plan.intent == "kpi":
        options = [f"Show {label} by month"] + by_dim + [f"Compare {label} with the previous month"]
    elif plan.intent == "trend":
        options = by_dim + ["Only the last three months"] + why
    elif plan.intent in ("breakdown", "ranking"):
        options = ["Only the last three months", "Compare it with the previous period", f"Show {label} by month"]
    else:
        options = [f"Show {label} by month"] + by_dim + ["Only the last three months"]
    return options[:3]


def generate_suggestions_by_intent(plan: Plan, semantic: Optional[SemanticLayer] = None) -> List[str]:
    """Generates intelligent follow-up suggestions for the user."""
    if semantic is not None and not _is_retail(semantic):
        return _generic_suggestions(plan, semantic)
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

    # Every query is bounded by a time window, and a row with no readable date
    # falls outside all of them. So an issue on the time column changes the answer
    # even when the plan never names that column - and it is listed first, so the
    # cap below can never push it out.
    time_col = plan.time.column if plan.time and plan.time.column else semantic.time.primary_column
    if time_col:
        used_cols.add(time_col)

    time_warnings = []
    warnings = []
    for issue in semantic.quality_issues:
        iss_tbl = issue.get("table")
        iss_col = issue.get("column")
        if iss_col and f"{iss_tbl}.{iss_col}" in used_cols:
            (time_warnings if f"{iss_tbl}.{iss_col}" == time_col else warnings).append(issue)
        elif not iss_col and iss_tbl in used_tables:
            warnings.append(issue)

    return (time_warnings + warnings)[:3]

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

    # Marker so we can report the LLM usage for this turn alone, not the process total.
    stats_mark = STATS.current_seq()

    norm_q = question.strip().lower()
    # The same words mean different things in different conversations ("break it
    # down by region" patches whatever plan came before), so the plan the session
    # is currently holding is part of the key.
    context = json.dumps(session.current_plan, sort_keys=True, default=str) if session.current_plan else ""
    cache_key = f"{session.dataset_id}:{norm_q}:{context}"

    # Fast-path cache hit for instant demo responses (<50ms)
    if cache_key in _DEMO_QUERY_CACHE:
        cached_resp = dict(_DEMO_QUERY_CACHE[cache_key])
        # Replay must leave the session exactly as a live answer would, or the next
        # follow-up patches a stale plan.
        session.current_plan = cached_resp.get("plan")
        cached_rows = (cached_resp.get("result") or {}).get("rows")
        if cached_rows:
            session.last_result_head = {
                "columns": (cached_resp["result"].get("columns") or [])[:5],
                "rows": cached_rows[:5],
            }
        session.history.append(Turn(
            turn=len(session.history) + 1,
            question=question,
            plan=cached_resp.get("plan"),
            summary=(cached_resp.get("narrative") or "")[:100]
        ))
        save_session(session)
        logger.info(f"Serving cached demo query response for: '{question}'")
        # A replayed answer cost nothing, so it must not inflate this turn's usage.
        cached_resp["from_cache"] = True
        cached_resp["llm_stats"] = STATS.turn_summary(STATS.current_seq())
        cached_resp["llm_totals"] = STATS.summary()
        return cached_resp

    # 1. LLM Planning with network-resilient heuristic fallback
    current_plan_dict = session.current_plan
    used_heuristic_fallback = False
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
        used_heuristic_fallback = True
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
            "suggestions": (
                ["Show total revenue", "Monthly revenue for 2026", "Create management dashboard"]
                if _is_retail(semantic) else starter_suggestions(semantic)
            ),
            "mode": "plan",
            "from_cache": False,
            "llm_stats": STATS.turn_summary(stats_mark),
            "llm_totals": STATS.summary(),
        }

    def _resolve_and_validate(out: PlannerOutput):
        # 2. Follow-up Patch or New Plan
        # `changes` may legitimately be an empty dict - a follow-up that alters no
        # fields, such as "show that as a pie chart". Testing it for truthiness would
        # drop the current plan and reset to a default KPI, so test for presence.
        if out.is_follow_up and out.changes is not None and current_plan_dict:
            resolved = patch_plan(current_plan_dict, out.changes)
        else:
            resolved = out.plan or Plan(
                intent="kpi", metric=semantic.metrics[0].name if semantic.metrics else None
            )

        # Heal intent if question clearly indicates a "why" root cause inquiry
        q_lower = question.lower()
        why_keywords = ["why did", "why has", "why is", "why was", "why were", "what caused", "explain drop", "explain fall", "explain decline", "reason for drop", "reason for fall", "why"]
        if any(kw in q_lower for kw in why_keywords) and resolved.intent != "why":
            resolved.intent = "why"

        # 3. Validate Plan
        return validate_plan(resolved, semantic)

    plan, errors, val_assumptions = _resolve_and_validate(planner_out)

    # A rejected plan gets exactly one re-plan, told what the validator refused. That
    # turns "the model swapped the metric and a grouping column" from a dead end into
    # a correction; it is skipped where no plan could help (no date column, no metric)
    # and for the heuristic fallback, which has no model to ask.
    unfixable = ("NO_TIME_COLUMN", "NO_METRICS")
    if errors and not used_heuristic_fallback and not any(e.startswith(unfixable) for e in errors):
        try:
            retry_out = plan_query(
                question=question,
                semantic=semantic,
                value_index=value_index,
                current_plan=current_plan_dict,
                recent_turns=[{"question": t.question, "summary": t.summary} for t in session.history[-3:]],
                last_result_head=session.last_result_head,
                validation_feedback="; ".join(e.split(": ", 1)[-1] for e in errors),
            )
            if retry_out.status == "ok":
                retry_plan, retry_errors, retry_notes = _resolve_and_validate(retry_out)
                if not retry_errors:
                    logger.info("Re-plan after validation errors succeeded (%s)", "; ".join(errors))
                    planner_out, plan, errors, val_assumptions = retry_out, retry_plan, retry_errors, retry_notes
        except Exception as exc:
            logger.warning("Re-plan after validation errors failed (%s); keeping the first result.", exc)

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
            # Say why, not just that it failed: "UNKNOWN_METRIC: ..." -> the sentence after the code.
            "narrative": "I couldn't run that question. " + " ".join(
                e.split(": ", 1)[-1] for e in errors
            ),
            "dq_warnings": [],
            "why": None,
            "suggestions": starter_suggestions(semantic),
            "mode": "plan",
            "from_cache": False,
            "llm_stats": STATS.turn_summary(stats_mark),
            "llm_totals": STATS.summary(),
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
        metric_name = plan.metric if isinstance(plan.metric, str) else (
            semantic.metrics[0].name if semantic.metrics else ""
        )
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
    metric_additive = True
    if isinstance(plan.metric, str):
        m_obj = next((m for m in semantic.metrics if m.name == plan.metric), None)
        if m_obj:
            metric_format = m_obj.format
            metric_additive = m_obj.additive

    # The chart type the user asked for ("bar graph", "as a table") is read from
    # their own words. The planner is never asked for it, and the plan is unchanged.
    chart_request = parse_chart_request(question)
    chart = select_chart(
        plan, result, metric_format,
        requested=chart_request.kind if chart_request else None,
        additive=metric_additive,
    )
    if chart_request:
        note = chart_request_note(chart_request, chart["type"])
        if note and note not in all_assumptions:
            all_assumptions = all_assumptions + [note]

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

    suggestions = generate_suggestions_by_intent(plan, semantic)

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
    # Cache the analysis, not the telemetry - a replay has its own (zero) usage.
    # A heuristic-fallback answer is a stand-in for one the LLM failed to plan, and
    # a follow-up only makes sense against the plan that preceded it. Caching either
    # would keep replaying the wrong chart long after the cause was fixed.
    if not used_heuristic_fallback and not planner_out.is_follow_up:
        _DEMO_QUERY_CACHE[cache_key] = dict(resp)
    resp["from_cache"] = False
    resp["llm_stats"] = STATS.turn_summary(stats_mark)
    resp["llm_totals"] = STATS.summary()
    return resp

