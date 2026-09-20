from pathlib import Path
from typing import Any, Dict, List, Optional
from app.llm.client import complete_chat
from app.narrator.verify import verify_narrative
from app.planner.plan_schema import Plan

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "llm" / "prompts"

def load_narrator_prompt() -> str:
    path = PROMPTS_DIR / "narrator.md"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "Explain the data analysis results in 2-3 concise sentences using only provided numbers."

def compute_derived_stats(plan: Plan, result: Dict[str, Any]) -> Dict[str, Any]:
    """Computes basic aggregates in Python so the LLM doesn't have to do math."""
    derived = {}
    rows = result.get("rows", [])
    cols = result.get("columns", [])
    if not rows:
        return derived

    if "current" in cols and "previous" in cols and "delta" in cols:
        cur_sum = sum(r[cols.index("current")] for r in rows if r[cols.index("current")] is not None)
        prev_sum = sum(r[cols.index("previous")] for r in rows if r[cols.index("previous")] is not None)
        delta = cur_sum - prev_sum
        pct = round((delta / prev_sum) * 100, 1) if prev_sum else 0.0
        derived["total_current"] = round(cur_sum, 2)
        derived["total_previous"] = round(prev_sum, 2)
        derived["total_delta"] = round(delta, 2)
        derived["total_delta_pct"] = pct
        derived["direction"] = "fell" if delta < 0 else ("rose" if delta > 0 else "flat")

    elif len(cols) == 2 and rows:
        # Breakdown / Ranking
        vals = [r[1] for r in rows if isinstance(r[1], (int, float))]
        if vals:
            tot = sum(vals)
            top_r = rows[0]
            top_val = top_r[1]
            derived["total"] = round(tot, 2)
            derived["top_item"] = str(top_r[0])
            derived["top_value"] = round(top_val, 2)
            derived["top_share"] = round((top_val / tot) * 100, 1) if tot > 0 else 0.0

    return derived

def generate_templated_narrative(
    plan: Plan,
    result: Dict[str, Any],
    period_label: str,
    baseline_label: Optional[str] = None
) -> str:
    """Deterministic fallback narrative."""
    rows = result.get("rows", [])
    cols = result.get("columns", [])
    if not rows:
        return f"No records found for the period {period_label}."

    metric_name = plan.metric if isinstance(plan.metric, str) else "Metric"
    metric_title = metric_name.replace("_", " ").title()

    if plan.intent == "kpi" and len(rows) == 1:
        if "delta" in cols:
            r = rows[0]
            cur = r[cols.index("current")]
            delta = r[cols.index("delta")]
            dp = r[cols.index("delta_pct")]
            dir_word = "fell" if delta < 0 else "rose"
            return f"{metric_title} for {period_label} was {cur:,.2f}, which {dir_word} by {abs(delta):,.2f} ({dp}%) compared to {baseline_label or 'the previous period'}."
        else:
            return f"Total {metric_title.lower()} for {period_label} was {rows[0][0]:,.2f}."

    if len(cols) >= 2 and rows:
        top_item = rows[0][0]
        top_val = rows[0][1]
        vals = [r[1] for r in rows if isinstance(r[1], (int, float))]
        tot = sum(vals) if vals else 1
        share = round((top_val / tot) * 100, 1) if tot > 0 else 0
        return f"For {period_label}, {top_item} is the leading segment with {top_val:,.2f} ({share}% of total {metric_title.lower()})."

    return f"Analysis complete for {period_label} showing {len(rows)} results."

def narrate_result(
    question: str,
    plan: Plan,
    result: Dict[str, Any],
    period_label: str,
    baseline_label: Optional[str] = None,
    dq_warnings: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Generates a natural language explanation and verifies its numbers against DuckDB outputs.
    Falls back to deterministic template if verification fails or model errors.
    """
    derived = compute_derived_stats(plan, result)

    system_prompt = load_narrator_prompt()
    user_prompt = f"""
<question>{question}</question>
<plan>{plan.model_dump_json()}</plan>
<period>{period_label}{f' vs {baseline_label}' if baseline_label else ''}</period>
<result_columns>{result.get('columns', [])}</result_columns>
<result_rows>
{result.get('rows', [])[:20]}
</result_rows>
<derived_stats>{derived}</derived_stats>
<data_quality_notes>{[w.get('impact') for w in (dq_warnings or [])]}</data_quality_notes>
"""

    try:
        raw_text = complete_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
            max_tokens=300
        ).strip()

        # Number verification
        is_valid, offending = verify_narrative(raw_text, result, derived)
        if is_valid:
            return raw_text
        else:
            # Fallback to templated summary if hallucination detected
            return generate_templated_narrative(plan, result, period_label, baseline_label)
    except Exception:
        return generate_templated_narrative(plan, result, period_label, baseline_label)
