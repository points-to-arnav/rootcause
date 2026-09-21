"""
Reads an explicit chart-type request out of the user's own wording.

"show me the bargraph by month", "make it a line chart", "as a table" - the chart
type is presentation, and the selector cannot guess it from the result alone. It is
read here, from the question text, with plain patterns: no LLM, no plan schema
change, and the same answer for the same words every time.

A type the UI cannot draw (pie, scatter...) is returned as a bar request with a
note saying so, so the user is told rather than silently given something else.
"""
import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class ChartRequest:
    kind: str                    # "bar" | "bar_h" | "line" | "table"
    note: Optional[str] = None   # set when the type asked for cannot be drawn


_WORD_END = r"(?:graph|chart|plot|diagram)s?"

# (pattern, kind, note). Order does not matter: the last mention in the sentence wins.
_PATTERNS = [
    (re.compile(rf"\bhorizontal\s*-?\s*bar\s*-?\s*{_WORD_END}?", re.I), "bar_h", None),
    (re.compile(rf"\bbar\s*-?\s*{_WORD_END}|\bbar{_WORD_END}|\bcolumn\s*-?\s*{_WORD_END}|\bhistograms?\b|\b(?:in|as|with)\s+bars\b", re.I), "bar", None),
    (re.compile(rf"\bline\s*-?\s*{_WORD_END}|\bline{_WORD_END}|\barea\s*-?\s*{_WORD_END}", re.I), "line", None),
    (re.compile(r"\b(?:as|in)\s+(?:a\s+)?(?:table|tabular)\b|\btabular\b|\btable\s+(?:view|format)\b|\b(?:a|the)\s+table\s+of\b", re.I), "table", None),
]

_UNSUPPORTED = [
    (re.compile(r"\bpie\b|\bpiechart", re.I), "Pie"),
    (re.compile(r"\bdonut\b|\bdoughnut\b", re.I), "Donut"),
    (re.compile(r"\bscatter\s*-?\s*(?:plot|graph|chart)?", re.I), "Scatter"),
    (re.compile(r"\bheat\s*-?\s*map\b", re.I), "Heatmap"),
    (re.compile(r"\bradar\b|\bspider\s+chart\b", re.I), "Radar"),
    (re.compile(r"\bbubble\s*-?\s*(?:chart|plot)?", re.I), "Bubble"),
    (re.compile(r"\btree\s*-?\s*map\b", re.I), "Treemap"),
    (re.compile(r"\bfunnel\b", re.I), "Funnel"),
    (re.compile(r"\bgauge\b", re.I), "Gauge"),
    (re.compile(r"\bbox\s*-?\s*(?:and\s*-?\s*whisker\s*)?plot\b|\bsankey\b", re.I), "Box"),
]

# "not a line graph", "instead of the pie chart": a type named in order to be refused.
# Only a few filler words may sit between the negation and the type, so "no idea,
# show a bar chart" is not read as a refusal of bar charts.
_NEGATION = re.compile(
    r"\b(?:not|no|instead\s+of|rather\s+than|without|don'?t\s+want|stop\s+showing)"
    r"(?:\s+(?:a|an|the|any|another|more|use|using|show|showing|as|in|with)){0,3}\s*$",
    re.I,
)


# What each requested kind is satisfied by. A grouped bar is still a bar chart, and
# a horizontal bar is still a bar graph; the reverse is not true.
_SATISFIED_BY = {
    "bar": {"bar", "bar_h", "grouped_bar", "contribution"},
    "bar_h": {"bar_h"},
    "line": {"line"},
    "table": {"table"},
}
_LABEL = {
    "bar": "bar chart", "bar_h": "horizontal bar chart", "line": "line chart",
    "grouped_bar": "grouped bar chart", "table": "table", "kpi": "single figure",
    "contribution": "contribution chart",
}


def chart_request_note(request: ChartRequest, shown: str) -> Optional[str]:
    """
    A sentence for the user when what was drawn is not what they asked for, or None
    when it was honoured. Said plainly, so a request is never silently ignored.
    """
    if shown in _SATISFIED_BY[request.kind]:
        return request.note   # an unavailable type (pie...) still gets its own note
    asked = _LABEL[request.kind]
    return f"Showing a {_LABEL.get(shown, shown)} instead of a {asked}: a {asked} does not fit this result."


def parse_chart_request(question: str) -> Optional[ChartRequest]:
    """Returns the chart type the question asks for, or None when it asks for none."""
    text = question or ""
    mentions: List[tuple] = []   # (start, end, ChartRequest)

    for pattern, kind, note in _PATTERNS:
        for match in pattern.finditer(text):
            mentions.append((match.start(), match.end(), ChartRequest(kind, note)))

    for pattern, name in _UNSUPPORTED:
        for match in pattern.finditer(text):
            note = f"{name} charts aren't available; showing this as a bar chart."
            mentions.append((match.start(), match.end(), ChartRequest("bar", note)))

    # "horizontal bar chart" also contains "bar chart"; the longer phrase is the
    # intended one, so a mention lying inside another mention is dropped.
    mentions = [
        m for m in mentions
        if not any(o is not m and o[0] <= m[0] and m[1] <= o[1] and (o[1] - o[0]) > (m[1] - m[0])
                   for o in mentions)
    ]

    # A type the user is turning away from is not the type they want.
    wanted = [
        m for m in mentions
        if not _NEGATION.search(text[max(0, m[0] - 24):m[0]])
    ]
    if not wanted:
        return None
    return max(wanted, key=lambda m: m[0])[2]
