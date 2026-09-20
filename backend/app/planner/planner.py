import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from app.llm.client import complete_json
from app.planner.plan_schema import PlannerOutput, Plan
from app.semantic.model import SemanticLayer
from app.semantic.value_index import ValueIndex

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "llm" / "prompts"

def load_system_prompt() -> str:
    path = PROMPTS_DIR / "planner.md"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "You are the query planner. Output valid JSON only conforming to PlannerOutput."

def format_schema_context(semantic: SemanticLayer) -> str:
    lines = []
    for tname, tmeta in semantic.tables.items():
        cols_desc = []
        for cname, cmeta in tmeta.columns.items():
            sample_str = f"[{', '.join(str(s) for s in cmeta.samples[:4])}]" if cmeta.samples else ""
            cols_desc.append(f"{cname}:{cmeta.role}:{cmeta.dtype}{sample_str}")
        lines.append(f"Table {tname} ({tmeta.role}, {tmeta.row_count} rows): " + "; ".join(cols_desc))
    
    # Joins
    joins_desc = [f"{r.from_col} -> {r.to_col}" for r in semantic.relationships]
    lines.append("Relationships: " + (", ".join(joins_desc) if joins_desc else "None"))
    return "\n".join(lines)

def format_metrics_context(semantic: SemanticLayer) -> str:
    lines = []
    for m in semantic.metrics:
        syn = f"[synonyms: {', '.join(m.synonyms[:3])}]" if m.synonyms else ""
        lines.append(f"- {m.name}: {m.label} ({'additive' if m.additive else 'non-additive'}, time: {m.time_behavior}) {syn}")
    return "\n".join(lines)

def plan_query(
    question: str,
    semantic: SemanticLayer,
    value_index: Optional[ValueIndex] = None,
    current_plan: Optional[Dict[str, Any]] = None,
    recent_turns: Optional[List[Dict[str, Any]]] = None,
    last_result_head: Optional[Dict[str, Any]] = None
) -> PlannerOutput:
    """
    Translates user's question into structured PlannerOutput using LLM.
    """
    system_prompt = load_system_prompt()

    # Find value matches
    value_matches = []
    if value_index:
        matches = value_index.search_question(question, score_threshold=85.0)
        for m in matches[:6]:
            if m["kind"] == "value":
                value_matches.append(f"'{m['term']}' -> {m['target']} = '{m['value']}'")
            elif m["kind"] == "metric":
                value_matches.append(f"'{m['term']}' -> metric {m['target']}")

    user_prompt = f"""
<schema>
{format_schema_context(semantic)}
</schema>

<metrics>
{format_metrics_context(semantic)}
</metrics>

<time_info>
Data range: {semantic.time.min} to {semantic.time.max}; Latest date (anchor): {semantic.time.anchor_date}
</time_info>

<value_matches>
{chr(10).join(value_matches) if value_matches else "None"}
</value_matches>

<current_plan>
{current_plan if current_plan else "none"}
</current_plan>

<recent_turns>
{recent_turns if recent_turns else "none"}
</recent_turns>

<last_result_head>
{last_result_head if last_result_head else "none"}
</last_result_head>

<question>
{question}
</question>
"""

    return complete_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_cls=PlannerOutput,
        temperature=0.1,
        max_tokens=600
    )
