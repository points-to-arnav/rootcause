# viz-rules.md: Result Shape → Chart

Deterministic mapping in `viz/selector.py`. The backend chooses the chart type and emits an ECharts option (or a KPI payload); the frontend renders it and applies number/date formatters (`frontend.md` section 6). The LLM does not choose charts.

## 1. Inputs
The selector receives the executed `Plan`, the result columns with their kinds, and the result size. Column kinds: `time` (period column), `dimension` (string), `measure` (numeric), `delta`, `delta_pct`, `current`, `previous`.

## 2. Selection table (first matching row wins)
| # | Condition | `chart.type` | Notes |
|---|---|---|---|
| 1 | `intent = why` | `contribution` | signed horizontal bars of segment contributions for the top driver dimension; drill path shown separately |
| 2 | `intent = detail`, or more than 2 dimension columns, or result has no measure | `table` | |
| 3 | 1 row and 1 measure | `kpi` | with `previous`, `delta`, `delta_pct` when compared |
| 4 | time column + measure(s), no dimension | `line` | one series |
| 5 | time column + measure + 1 dimension | `line` (multi-series) | up to 6 series; otherwise top 5 by total plus "Other" |
| 6 | comparison columns (`current`, `previous`) with 1 dimension | `grouped_bar` | two bars per category; sorted by `sort` |
| 7 | 1 dimension + measure, `intent = ranking` or more than 12 categories or long labels (over 18 characters) | `bar_h` | sorted; top N shown; first item at top |
| 8 | 1 dimension + measure, up to 12 categories | `bar` | sorted descending unless the dimension is ordinal (see below) |
| 9 | 2 dimensions + measure | `bar` grouped by the second dimension (up to 6 groups), otherwise `table` | |
| 10 | anything else | `table` | |

**Requested chart type.** The LLM still does not choose charts, but the *user* can. `viz/chart_request.py` reads an explicit type from the question text ("bar graph", "horizontal bar chart", "line chart", "as a table"); `select_chart(..., requested=)` honours it whenever the result's shape can carry it:

| Asked for | Shape | Result |
|---|---|---|
| bar | time series, or time + dimension | vertical bars, chronological (never flipped horizontal) |
| bar | breakdown / ranking | the selector's own `bar` / `bar_h` choice (both are bar graphs) |
| horizontal bar | any 2-column result | `bar_h` |
| line | time series | `line` |
| line | category breakdown | not forced (a line implies an order): bars, with a note |
| table | anything except `why` and a single figure | `table` (the UI opens on the table view) |
| bar / line | single figure, `why` | `kpi` / `contribution` unchanged; a note says why |
| pie, donut, scatter, heatmap... | any | bars, with a note that the type is unavailable |

Whenever what is drawn differs from what was asked, one sentence is added to `assumptions` (never silently ignored). The plan schema and API contract are unchanged.

**Period + dimension + measure** (three columns from a `trend` with a dimension) draws one series per dimension value: lines by default, grouped bars when bars are requested. More than 6 series: top 5 plus "Other" for an additive measure; a `table` for a non-additive one (an average cannot be summed).

**Ordinal dimensions** (keep natural order instead of sorting by value): month names, weekdays, quarters, numeric bins, years, ratings.

**Always:** a table view is available as a toggle (`ResultTable`). No pie or donut charts by default.

## 3. ECharts option skeletons
Numbers are raw; formatters are added by the frontend.

**Line**
```json
{"tooltip": {"trigger": "axis"},
 "grid": {"left": 12, "right": 16, "top": 24, "bottom": 8, "containLabel": true},
 "xAxis": {"type": "category", "data": ["2026-01", "2026-02"]},
 "yAxis": {"type": "value", "name": "Revenue"},
 "series": [{"type": "line", "name": "Revenue", "data": [1, 2], "showSymbol": true}]}
```
Multi-series adds a `legend` (top) and one series per group. Period labels come from the ISO period start.

**Vertical bar**
```json
{"tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
 "xAxis": {"type": "category", "data": ["West", "East"]},
 "yAxis": {"type": "value"},
 "series": [{"type": "bar", "data": [3, 2]}]}
```

**Horizontal bar (`bar_h`)**
```json
{"tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
 "grid": {"left": 12, "right": 48, "top": 8, "bottom": 8, "containLabel": true},
 "xAxis": {"type": "value"},
 "yAxis": {"type": "category", "inverse": true, "data": ["Product A", "Product B"]},
 "series": [{"type": "bar", "data": [3, 2], "label": {"show": true, "position": "right"}}]}
```
`inverse: true` puts the first (largest) item at the top.

**Grouped bar:** two `bar` series (`Previous`, `Current`) sharing the category axis; legend at top.

**Contribution (why):** horizontal bars of signed contribution (share of the total change) per segment, positive and negative coloured differently, zero line visible, the driver segment highlighted, at most 10 segments (rest grouped as "Other"). Data items use `{"value": -0.83, "itemStyle": {"color": "..."}}`. Tooltip shows delta, contribution %, baseline share.

**KPI payload:** `{"kpi": {"value": 4100000, "previous": 4850000, "delta": -750000, "delta_pct": -15.5}}`, rendered by `KpiCard` (not ECharts). Sparklines on the dashboard use a minimal line option (no axes, no tooltip labels).

## 4. Colours
- Categorical palette (colour-blind safe, max 6 distinct): `#4C78A8`, `#F58518`, `#54A24B`, `#B279A2`, `#9D755D`, `#72B7B2`; "Other" in `#BAB0AC`.
- Sequential single-series charts use `#4C78A8`.
- Comparison: previous `#BAB0AC` (grey), current `#4C78A8`.
- Diverging (contribution): decrease `#D64545`, increase `#2E8B57`; the sign of the value decides, not the metric's meaning. For metrics where a decrease is good (e.g. costs, returns) the colour mapping is inverted via the metric's `good_direction` (default `up`).
- Severity: high `#D64545`, medium `#E69F00`, low `#4C78A8`, always with an icon and text.

## 5. Formatting rules
- Titles: metric label plus period, e.g. "Revenue by region · Mar-Aug 2026". Comparison charts add "vs Sep 2025-Feb 2026".
- Value axes start at zero for bars; line charts may use a data-fitted range but never truncate silently (the axis shows its start).
- Category labels longer than 18 characters are truncated with an ellipsis and the full text in the tooltip.
- More than 12 categories in a vertical bar switches to `bar_h` with the top 12 plus "Other" when the metric is additive.
- Percentages have one decimal; large numbers use compact notation on axes and full grouping in tooltips.
- Snapshot metrics (inventory) state "as of <date>" in the subtitle.
- Empty result: no chart, a message with the data range.
- Truncated results show a note: "Showing the first N rows".

## 6. Tests (`viz/selector.py`)
Table-driven tests: one row per selection rule with a synthetic result; ordinal handling; top-5-plus-Other for more than 6 series; contribution chart from a `WhyResult`; KPI payload with and without comparison; each output serialises to JSON and contains no functions.
