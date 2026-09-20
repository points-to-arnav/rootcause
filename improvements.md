# RootCause / AskData: Evaluation Feedback & Strategic Improvements

> **Document Status**: Active / Planning  
> **Source**: Evaluation Team Feedback & Technical Audit  
> **Target Areas**: UX/UI Modernization, Token Optimization, and Interactive Pipeline Loading Experience  

---

## Executive Summary

Following review by the evaluation team, three primary user-experience and architectural bottlenecks were identified:

1. **User Interface Friendliness & Aesthetics**: The current interface looks like a "generic AI wrapper" chatbot with plain cards. It lacks direct-manipulation affordances, visual polish, and intuitive data exploration workflows for non-technical users.
2. **Token Optimization**: Prompts dump entire table schemas, column samples, and historical plans indiscriminately on every query turn, leading to high token burn, latency spikes, and potential context window exhaustion.
3. **Pipeline Loading Experience**: The single spinning icon with static text (`"Analyzing question & executing DuckDB query..."`) feels plain, unresponsive, and creates uncertainty during multi-step analytical processing.

This document outlines the detailed problem analysis, technical designs, and implementation specifications to resolve each of these issues.

---

## 1. UI / UX Modernization (Overcoming the "Generic AI" Feel)

### 1.1 The Problem
- The current layout is a standard chat thread that treats analytical inquiry as a simple text message exchange.
- Users have no direct visual affordance to explore their dataset without typing full natural language prompts.
- Cards are passive: clicking on a chart bar, table row, or KPI card does not offer interactive drill-down or filtering.
- Visual styling feels like an off-the-shelf template rather than a specialized executive analytics platform.

### 1.2 Target Design Vision
- **Workspace Model (Linear / Vercel / Raycast Aesthetic)**:
  - **Left Sidebar**: Active Dataset Inspector (tables, column dictionary, metric dictionary, data quality indicators).
  - **Center Canvas**: Interactive Analysis Stream featuring card hero metrics, synchronized chart brushings, and multi-view comparisons (Chart / Table / SQL / Plan).
  - **Right Inspector Drawer**: Quick Filters, Slice-and-Dice controls, and automated driver analysis.
- **Direct Manipulation & Click-to-Drill**:
  - Clicking any bar in a breakdown chart automatically generates a contextual drill-down chip (e.g. `Click on 'Electronics' -> [Drill: Category = 'Electronics']`).
  - Hover tooltips display contextual contribution and share statistics rather than just raw values.
- **Quick Action Command Palette (`Cmd + K` / `Ctrl + K`)**:
  - Instant jumping between dataset tables, common KPI calculations, and executive dashboard exports.
- **Stitch MCP Integration**:
  - Utilize Stitch MCP to design, prototype, and render production-grade, human-centered UI screens that eliminate generic chatbot patterns.

---

## 2. Token Optimization & Prompt Compression

### 2.1 The Problem
In [planner.py](file:///e:/workflow/rootcause/backend/app/planner/planner.py), every user query sends:
- Full schemas for all tables (`format_schema_context`).
- All column names, data roles, and 4 sample values per column.
- Complete join relationship lists.
- Full metric definitions and synonyms.
- Full JSON plans from past turns and head samples of previous query results.

For a dataset with 8 tables and 100 columns, this injects **1,500–3,500 tokens of boilerplate per query**, resulting in:
- High latency (1.5–3.0s waiting for prompt transmission and processing).
- Unnecessary API token costs.
- Model distraction by irrelevant columns.

### 2.2 Technical Solutions

#### A. Relevant Column & Table Pruning
- Do not send the entire schema on every query.
- Use the `ValueIndex` and question n-grams to identify candidate tables and columns.
- Inject only:
  - The primary fact table.
  - Tables directly referenced or reachable via join paths.
  - Columns matching the user's inquiry or registered metrics.

#### B. Compact Semantic DSL Representation
Replace verbose prose/JSON with a token-dense schema format:
```text
# Before (Verbose, ~250 tokens per table):
Table sales (fact, 16600 rows): order_id:id:VARCHAR[]; order_date:time:DATE[]; amount:measure:DOUBLE[]; product_id:id:VARCHAR[]; customer_id:id:VARCHAR[]

# After (Compact DSL, ~60 tokens per table):
T:sales(fact,16.6k)|pk:order_id|time:order_date|m:amount|fk:product_id->products.id,customer_id->customers.id
```

#### C. Prompt Caching Structure
- Restructure the prompt into two distinct tiers:
  1. **Static / Cacheable Block**: System instructions, schema ontology DSL, and metric registry. This allows providers (OpenAI / Anthropic) to utilize **prompt caching**, reducing token costs and cut latency by up to 80%.
  2. **Dynamic Turn Block**: Current question, minimal conversation summary, and active filters.

#### D. Turn History Compression
- Instead of serializing full JSON plans for past turns (`session.history`), store only a 1-line semantic summary:
  - *Turn 1*: `Plan: trend(revenue, month, 2026)`
  - *Turn 2*: `Plan: breakdown(revenue, region, Last 1M)`
- Pass only the last 2 turns instead of 3–5 full objects.

---

## 3. Interactive Multi-Stage Loading Experience

### 3.1 The Problem
- The current loading state in [AnalystPage.tsx](file:///e:/workflow/rootcause/frontend/src/pages/AnalystPage.tsx) is a plain spinner:
  ```tsx
  <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
  <span>Analyzing question & executing DuckDB query...</span>
  ```
- Because analysis involves multiple distinct sub-operations (LLM planning $\to$ plan validation $\to$ DuckDB compilation $\to$ DuckDB execution $\to$ chart selection $\to$ narrative verification), a generic spinner feels slow, opaque, and uninformative.

### 3.2 Technical Solutions

#### A. Animated Multi-Stage Progress Stepper
Replace the plain spinner with a dynamic, phased pipeline indicator:
```
[1/4] ✦ Understanding query intent & resolving time window...
[2/4] ⚙ Compiling verified DuckDB SQL & join graph...
[3/4] ⚡ Executing deterministic calculation across 16.6k records...
[4/4] 📊 Rendering visual chart & verifying narrative facts...
```

#### B. Visual Shimmer & Skeleton Loaders
- Render pulse-shimmer skeleton blocks mimicking the final layout:
  - Skeleton KPI card or chart container with pulsing gradients.
  - Animated narrative text placeholder lines.
- This creates perceived zero-latency responsiveness while the query completes.

#### C. Micro-Telemetry
- Display real-time execution telemetry upon completion:
  - `"DuckDB: 12ms • Rows: 8 • Verified: 100%"`
- Gives the user confidence that deterministic computation occurred rather than an LLM hallucination.

---

## 4. Implementation Matrix & Prioritization

| Phase | Task | Target Components | Impact | Complexity |
|---|---|---|---|---|
| **Phase 1** | **Multi-Stage Loading Stepper** | `AnalystPage.tsx`, `useAppStore.ts` | Immediate UX upgrade; transparent pipeline status | Low |
| **Phase 2** | **Token Optimization (DSL & Schema Pruning)** | `planner.py`, `client.py` | 60%+ reduction in prompt tokens; 2x faster planning | Medium |
| **Phase 3** | **Interactive Chart Drill-Down & Filters** | `AnswerCard.tsx`, `ChartRenderer.tsx` | High interactivity; eliminates text-only chat feel | Medium |
| **Phase 4** | **Stitch MCP UI Redesign** | New screens via `StitchMCP` | Modern, custom-designed analytics workspace | High |

---

## 5. Next Steps

1. **Implement Phase 1**: Upgrade the loading animation to a multi-stage stepper with skeleton loaders.
2. **Implement Phase 2**: Compress planner prompt representations and activate token caching.
3. **Execute UI Redesign via Stitch MCP**: Generate wireframes and production screens matching the modern workspace vision.
