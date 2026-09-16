# Master Agent → Subagent → data_to_chart: Working Reproduction

Counter-example to the reported issue: *"unable to render interactive charts when
using a Master Agent–Subagent architecture."*

**Conclusion: charts do render.** The master agent invokes `data_to_chart` on
data produced through the subagent and emits a `response.chart` event containing
a full Vega-Lite v5 spec.

Verified on account `SFPSCOGS-RRAMAN_AWS_SI`, Snowflake **10.32.102**, 14 Sep 2026.

---

## Contents

| Path | What it is |
|---|---|
| `EMAIL_TO_VISHWA.md` | Customer-facing email with screenshot placeholders and capture list |
| `deploy_repro.sql` | Full runnable example, top to bottom, with teardown |
| `screenshots/` | **Empty — drop the 5 captures here** (see email's capture list) |

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
| `01_PASS_top5_products_chart.log` | The exact question from the report → 5-row bar chart + full Vega-Lite spec |
| `02_PASS_monthly_trend_chart.log` | 12-row monthly trend → line chart |
| `03_PASS_inventory_two_charts.log` | Second semantic view → **two** charts in one turn |
| `04_FAIL_type_agent_invalid.log` | `type: agent` → `Tool type agent is not valid.` (code 399504) |
| `05_subagent_implicit_chart_counts.txt` | `chart_spec` present in subagent output despite no chart tool declared |
| `05_subagent_direct.log` | Subagent called directly (no master) for token comparison baseline |
| `06_subagent_implicit_chart_spec.txt` | The actual spec from that subagent response |
| `07_token_comparison_master_vs_subagent.txt` | Stream size and semantic context comparison: master (111K) vs subagent (121K) — master is smaller |
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

## Key findings

1. **`agent_toolset` is the only supported master→subagent mechanism.**
   `tool_resources.<name>.agent_name` — the key is `agent_name`, not `agent`.

2. **`type: agent` is a silent trap.** `CREATE AGENT` accepts it without error,
   then fails at run time. `CREATE AGENT` does no `tool_spec.type` validation at
   all — a nonsense type like `not_a_real_tool_type_xyz` also creates fine.

3. **`agent_toolset` is tool inheritance, not delegation.** The referenced
   agent's tools are flattened into the caller's tool set; the subagent never
   runs its own reasoning loop and its instructions are ignored. Because of the
   flattening, `sql_execution` runs in the **master's own turn**, which is
   exactly why `data_to_chart` has a real result set and charting works.

4. The report's premise — `data_to_chart` consuming `sql_execution` output from
   *within* a subagent — describes an architecture that doesn't exist in that
   form. There is no nested execution boundary to cross.

## Token cost analysis (`agent_toolset` flattening)

Follow-up question from the customer: *"it's passing the entire context in to
each sub agent making tokens 60-70% more."*

**Finding: not true for `agent_toolset`.** Semantic view schemas are loaded
lazily (on demand per tool call), not eagerly when the agent starts.

| | Master (toolset) | Subagent (direct) |
|---|---|---|
| Raw stream | 111,182 bytes | 121,295 bytes |
| Data payload | 110,501 chars | 120,657 chars |
| Semantic context | 71,922 chars | 76,651 chars |

The master was **0.92x** the size of the subagent, not 1.6-1.7x. The subagent
was slightly larger because its response instructions produce more text output.

For a sales-only question, the INVENTORY_SV schema appeared **zero times** in
the master's trace — the orchestrator selected `query_sales` and the inventory
schema was never fetched.

See `evidence/07_*`, `08_*`, `09_*` and `scripts/compare_streams.py`,
`check_inventory_leakage.py` for the raw analysis.

**Important caveat:** `agent_toolset` is tool inheritance, not true A2A
delegation. The subagent's instructions and reasoning loop are not applied. If
the customer needs subagent-level instruction isolation (e.g., different
personas or domain-specific reasoning per subagent), `agent_toolset` does not
provide that. The trade-off is: `agent_toolset` gives you charts but no
instruction isolation; custom A2A (`generic` tool wrapping `DATA_AGENT_RUN`)
gives you instruction isolation but breaks charting because the result comes
back as text, not a structured result set.

## Caveats (do not overstate to the customer)

- **UI render not yet captured.** The API traces prove `chart_spec` is emitted,
  which is the part the agent controls. The visual confirmation in the Snowflake
  Intelligence UI is still open — hence the screenshot list.
- **Chart capability may be implicit.** The subagent emitted a `chart_spec`
  despite having no `data_to_chart` tool, so "the master must own
  `data_to_chart`" is likely weaker than the docs imply. Doesn't change the
  conclusion.

## Deployed objects

```
CHART_SUBAGENT_DEMO.DEMO                          -- data + semantic views
  ├── PRODUCTS / SALES / INVENTORY
  ├── SALES_SV
  └── INVENTORY_SV

SNOWFLAKE_INTELLIGENCE.AGENTS.DEMO_DATA_SUBAGENT  -- owns both views, no chart tool
SNOWFLAKE_INTELLIGENCE.AGENTS.DEMO_MASTER_AGENT   -- owns data_to_chart, no views
```

Teardown is the commented block at the end of `deploy_repro.sql`.

## Running the harness

```bash
python scripts/run_agent.py \
  --agent DEMO_MASTER_AGENT \
  --question "Show me sales by product for the top 5 products." \
  --connection demo \
  --out trace.txt
```

Exit code `0` = a chart spec was emitted, `2` = no chart (the failure signal).
