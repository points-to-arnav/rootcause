# Prompt Efficiency in RootCause

How we cut the token cost of every question by ~75%, and why the system prompt is
built the way it is.

---

## 1. Where the LLM actually sits

RootCause is deliberately **not** an "LLM that answers questions about data". The
language model is used in exactly two narrow places:

| Stage | What the LLM does | What it never does |
|---|---|---|
| **Planner** | Turns English into a JSON query plan | Write SQL, compute anything |
| **Narrator** | Writes 2–3 sentences about numbers already computed | Invent or calculate a number |

Everything between those two steps — SQL compilation, joins, aggregation, the
root-cause decomposition — is deterministic Python and DuckDB. This matters for
efficiency as well as correctness: because the model only emits a small JSON
object and a short paragraph, **output tokens stay tiny**, and output tokens are
the expensive ones (on Claude Sonnet 5, $10/MTok out versus $2/MTok in — 5×).

---

## 2. The problem: the prompt repeats itself

To plan a query, the model needs to know the dataset: every table, column, role,
data type, the relationships between tables, the registered metrics, and the date
range. That schema block is roughly 800–1,500 tokens.

The catch is that this block is **identical for every question asked about the
same dataset**. Asking five questions about the retail demo meant sending the same
schema five times and paying full price five times.

---

## 3. The fix: split the prompt into stable and volatile halves

Prompt caching works on a **prefix match**. The provider hashes the front of your
request; if it matches a previous request byte for byte, that part is served from
cache at **0.1× the input price** instead of full price.

The requirement is strict: the cached part must come **first**, and it must be
byte-identical. Anything that changes between requests — a timestamp, a turn
counter, the user's question — must sit *after* the cache breakpoint, or the whole
entry is invalidated and you pay more than if you had never cached at all.

So we split the planner prompt in two:

```
┌─ STABLE PREFIX ──────────────── cached, billed at 0.1× after turn 1
│  planner.md          the instructions (~1,400 tokens)
│  <schema>            tables, columns, roles, relationships
│  <metrics>           revenue, units, orders, AOV, return_rate …
│  <time_info>         data range and anchor date
├─ ◄── cache breakpoint sits here
└─ VOLATILE TAIL ──────────────── billed fresh every time, but tiny
   <value_matches>     fuzzy matches for this question
   <current_plan>      the previous turn's plan
   <recent_turns>      short conversation history
   <question>          what the user actually typed
```

In code this is `build_dataset_context()` in `backend/app/planner/planner.py`,
which builds the stable half, and `stable_parts=[system_prompt, dataset_context]`
passed into the LLM client. The client hands those to whichever provider is
active.

**Key insight:** once caching works, schema size stops mattering much. We are not
forced to prune columns to save money — we pay for the schema once per session
and read it back cheaply thereafter.

---

## 4. Two providers, two mechanisms

**Anthropic API (direct).** We mark the breakpoint explicitly:

```python
blocks[-1]["cache_control"] = {"type": "ephemeral"}
```

One subtlety: below a model-specific floor the API **silently refuses** to create
a cache entry — no error, just `cache_creation_input_tokens: 0`. For Claude
Sonnet 5 that floor is **1,024 tokens**. Our code estimates the prefix size and
only sets the marker when it clears the floor, so we never waste a breakpoint.

**Claude Code CLI (local).** Each `claude -p` run is a *fresh process with no
local memory*. Nothing is saved on disk. The caching still happens — server-side
at Anthropic, keyed on the byte-exact prefix, with a 5-minute TTL. Because our
adapter sends the same `--system-prompt` every time, a second question hits the
same cache entry. Measured:

```
CALL 1  "What is our total revenue?"   write=2281  read=13209  cost=$0.0202
CALL 2  "Show revenue by region"       write=497   read=14992  cost=$0.0102
```

Different questions, same dataset — cost halved on the second one. A cache read
also **refreshes the 5-minute timer for free**, so a continuous demo keeps the
cache warm indefinitely.

---

## 5. Stripping the harness prompt (the biggest single win)

Claude Code normally ships its own system prompt — the coding harness, plus the
definitions of every built-in tool (Bash, Read, Edit, WebSearch…). That is about
**54,000 tokens on every call**, and it has nothing to do with data analysis.

Our adapter removes it in two steps:

| Configuration | Tokens per call |
|---|---|
| Default Claude Code invocation | 54,171 |
| `--system-prompt` replaces the harness prompt | 29,149 |
| `--disallowed-tools` removes all tool definitions | **13,724** |

**A 75% reduction**, before caching even applies. Disabling the tools is also a
correctness and safety decision: a query planner that could read the filesystem
is both slower and a liability.

---

## 6. Other efficiency choices

- **`max_tokens` raised from 600 to 1500** on the planner. Counter-intuitive, but
  600 truncated longer plans, and a truncated plan forces a retry — a retry is a
  *whole extra call*, far more expensive than the headroom.
- **A response cache** keyed on `dataset + question` replays repeated questions
  with **zero** model calls (`from_cache: true` in the API response).
- **Thinking disabled, effort `low`** on the Anthropic path. A schema-constrained
  JSON transformation is mechanical; extended reasoning adds seconds and cost for
  no accuracy gain.
- **`temperature` never sent** to Sonnet 5 — it returns a 400. Determinism comes
  from the prompt and from thinking being off.

---

## 7. The system prompt itself

Two prompt files live in `backend/app/llm/prompts/`.

**`planner.md`** is the larger one, and because it sits inside the cached prefix,
*length is cheap* — we pay for it once per session. It covers:

- **Scope and refusal.** Off-topic questions, general knowledge, advice, and
  prompt-injection attempts ("ignore previous instructions") all return
  `status: "unsupported"` with a short redirect. The user's message is explicitly
  framed as *data to plan over, never instructions to the model*.
- **Conversation types.** Greetings, meta questions ("what data do you have?"),
  ambiguous questions needing clarification, and eight query intents (`kpi`,
  `trend`, `breakdown`, `ranking`, `compare`, `why`, `detail`, `dashboard`).
- **Grounding rules.** Only tables, columns and metrics from `<schema>` may be
  named; values must come from `<value_matches>`; dates resolve against the
  dataset's own latest date, never today's.
- **Worked examples**, including the refusal cases.

**`narrator.md`** is short by design, because its input (the result rows) changes
every turn and cannot be cached. Its central rule is that every number must
already exist in the computed result. This is not merely a request: a regex
verifier (`backend/app/narrator/verify.py`) extracts every figure from the
model's sentence and checks it against the actual DuckDB output. If any number
fails, the model's text is **discarded** and replaced with a deterministic
template. That is the zero-hallucination guarantee.

---

## 8. Measured results

From a live three-question run against the retail demo:

| Metric | Value |
|---|---|
| Cache hit rate | **100%** (6/6 calls) |
| Prompt tokens served from cache | **89.3%** (85,682) |
| Cost | **$0.050** vs **$0.199** uncached |
| Saving | **74.9%** |

All of these are read from the provider's own usage reports — `cache_read_input_tokens`
and `cache_creation_input_tokens` — not estimated. They are surfaced live in the
UI's **Prompt cache** panel, with a per-answer breakdown under each result.

---

## 9. Likely viva questions

**Why not just use a smaller model?**
The planner's job is structured extraction against a schema — accuracy there
determines whether the SQL is correct at all. Caching lets us keep a capable model
at roughly the cost of a small one, which is a better trade than degrading the
step everything else depends on.

**Why does the question go last?**
Caching is a *prefix* match. Anything above the breakpoint that changes
invalidates the entry. The question is the most volatile part of the prompt, so it
must sit below it.

**What happens if caching fails?**
Nothing breaks. An uncached call is a normal call — it just costs full price. The
code also skips the breakpoint entirely when the prefix is below the model's
minimum, since a marker there would do nothing.

**Does the 1-hour TTL help?**
Only with gaps. Cache writes cost 1.25× at 5-minute TTL but **2×** at 1 hour, so
the longer TTL needs three requests to break even instead of two. Since reads
refresh the timer for free, continuous use keeps the cheap 5-minute cache warm
anyway.

**Where's the remaining headroom?**
Dropping `id` and free-text columns from the schema block (the planner can never
group by them), and trimming the narrator's row payload — it currently receives 20
result rows plus the full root-cause tree, all of it uncached.
