# Master Agent + Subagent + data_to_chart: Test Results

Testing whether interactive charts render when a master Cortex Agent reaches
semantic views through a subagent and owns the `data_to_chart` tool.

Verified on account `SFPSCOGS-RRAMAN_AWS_SI`, Snowflake **10.32.102**, 14 Sep 2026.

---

## Test setup

Two semantic views (Sales + Inventory), a subagent that owns both views (no
chart tool), and a master agent that owns `data_to_chart` but no views — reaching
data only through the subagent via `agent_toolset`.

```
CHART_SUBAGENT_DEMO.DEMO                          -- data + semantic views
  ├── PRODUCTS / SALES / INVENTORY
  ├── SALES_SV
  └── INVENTORY_SV

SNOWFLAKE_INTELLIGENCE.AGENTS.DEMO_DATA_SUBAGENT  -- owns both views, no chart tool
SNOWFLAKE_INTELLIGENCE.AGENTS.DEMO_MASTER_AGENT   -- owns data_to_chart, no views
```

`deploy_repro.sql` creates everything top to bottom. Teardown is the commented
block at the end.

---

## Contents

| Path | What it is |
|---|---|
| `deploy_repro.sql` | Full runnable example with teardown |
| `screenshots/` | Empty — for UI verification captures |

### `scripts/` — test and analysis harness

| Script | Purpose |
|---|---|
| `run_agent.py` | Calls an agent over REST SSE, dumps the raw event stream, flags `response.chart`. Exit 0 = chart emitted, 2 = no chart. |
| `compare_streams.py` | Compares raw stream sizes and semantic context payload sizes between master and subagent runs |
| `compare_tokens.py` | Attempts to extract token usage from SSE streams (agent API does not currently expose this) |
| `check_schema_loading.py` | Measures how much of the flattened semantic context is actually loaded per question |
| `check_inventory_leakage.py` | Checks whether the INVENTORY_SV schema appears in a sales-only question's master trace |
| `check_sub_inventory.py` | Same leakage check on the subagent-direct trace for comparison |
| `inspect_out.py` | Byte-level inspection of DATA_AGENT_RUN output |
| `count_needles.py` | Counts chart-related tokens (chart_spec, vega, data_to_chart) in a file |
| `grep_chart.py` | Extracts surrounding context around `chart_spec` occurrences |

### `evidence/` — run logs and analysis results

| File | Shows |
|---|---|
| `01_PASS_top5_products_chart.log` | Top-5 products question → 5-row bar chart + full Vega-Lite spec |
| `02_PASS_monthly_trend_chart.log` | 12-row monthly trend → line chart |
| `03_PASS_inventory_two_charts.log` | Second semantic view → **two** charts in one turn |
| `04_FAIL_type_agent_invalid.log` | `type: agent` → `Tool type agent is not valid.` (code 399504) |
| `05_subagent_implicit_chart_counts.txt` | `chart_spec` present in subagent output despite no chart tool declared |
| `05_subagent_direct.log` | Subagent called directly (no master) for token comparison baseline |
| `06_subagent_implicit_chart_spec.txt` | The actual spec from that subagent response |
| `07_token_comparison_master_vs_subagent.txt` | Stream size and semantic context comparison: master (111K) vs subagent (121K) |
| `08_schema_loading_analysis.txt` | Shows semantic view schemas are loaded lazily, not eagerly |
| `09_inventory_leakage_subagent_direct.txt` | Confirms subagent-direct also loads zero inventory context for a sales question |

### `evidence/raw_streams/` — full unedited SSE streams

| File | Source |
|---|---|
| `01_top5_products.sse.txt` | Master agent, top-5 products question |
| `02_monthly_trend.sse.txt` | Master agent, 12-month trend |
| `03_inventory.sse.txt` | Master agent, inventory question (two charts) |
| `04_type_agent_error.sse.txt` | Failed `type: agent` attempt |
| `05_subagent_direct.sse.txt` | Subagent called directly, same top-5 question |

---

## Test 1: Chart rendering with `agent_toolset`

**Result: charts render correctly across all three scenarios.**

The master agent's tool call sequence for "Show me sales by product for the top 5 products":

```
query_sales → system_execute_sql → server_skill → data_to_chart
```

Event stream output:
- `response.table` — tabular result set
- `response.chart` — full Vega-Lite v5 spec (`"mark": "bar"`, 5 data points)

Additional scenarios tested:
- 12-row monthly trend → line chart
- Cross-view inventory question → two charts in a single turn

---

## Test 2: `type: agent` vs `agent_toolset`

`agent_toolset` is the only supported mechanism for one agent to reference
another. It works by **tool inheritance** — the referenced agent's tools are
flattened into the caller's tool set at runtime. The subagent does not run its
own reasoning loop, and its instructions are not applied.

`type: agent` was also tested. `CREATE AGENT` accepts it without error, but the
agent fails at runtime:

```
{"message":"Tool type agent is not valid.","code":"399504"}
```

Note: `CREATE AGENT` performs no `tool_spec.type` validation — even a nonsense
type like `not_a_real_tool_type_xyz` creates successfully and only fails when
invoked.

---

## Test 3: Token cost of `agent_toolset` flattening

Tested the claim that toolset flattening passes the entire context to each
subagent, increasing tokens by 60-70%.

**Finding: semantic view schemas are loaded lazily (on demand per tool call),
not eagerly when the agent starts.**

| | Master (toolset) | Subagent (direct) |
|---|---|---|
| Raw stream | 111,182 bytes | 121,295 bytes |
| Data payload | 110,501 chars | 120,657 chars |
| Semantic context | 71,922 chars | 76,651 chars |

The master was **0.92x** the size of the subagent direct call, not 1.6-1.7x.
The subagent was slightly larger because its response instructions produce more
text output.

For a sales-only question, the INVENTORY_SV schema appeared **zero times** in
the master's trace — the orchestrator selected `query_sales` and the inventory
schema was never fetched.

See `evidence/07_*`, `08_*`, `09_*` and `scripts/compare_streams.py`,
`check_inventory_leakage.py` for the raw analysis.

---

## Key observations

1. **`agent_toolset` is tool inheritance, not A2A delegation.** The referenced
   agent's tools are flattened into the caller's tool set. SQL execution runs in
   the master's own turn, which is why `data_to_chart` has a real result set and
   charting works.

2. **The subagent's instructions are not applied.** If subagent-level instruction
   isolation is needed (e.g., different personas or domain-specific reasoning per
   subagent), `agent_toolset` does not provide that. A custom A2A pattern using a
   `generic` tool wrapping `DATA_AGENT_RUN` would preserve instruction isolation
   but returns data as text, which `data_to_chart` cannot consume as a structured
   result set.

3. **Chart generation may be implicit.** The subagent emitted a `chart_spec`
   despite having no `data_to_chart` tool declared, suggesting chart capability
   is available as a server-side skill regardless of explicit tool configuration.

4. **UI render not yet verified.** The API traces prove `chart_spec` is emitted.
   Visual confirmation in the Snowflake Intelligence UI is still open.

---

## Running the harness

```bash
python scripts/run_agent.py \
  --agent DEMO_MASTER_AGENT \
  --question "Show me sales by product for the top 5 products." \
  --connection demo \
  --out trace.txt
```

Exit code `0` = a chart spec was emitted, `2` = no chart.
