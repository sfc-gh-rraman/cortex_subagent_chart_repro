#!/usr/bin/env python3
"""
Raw Cortex Agent runner for the master-agent + subagent + data_to_chart repro.

Dumps the FULL raw SSE event stream so we can prove, with hard evidence, whether
the master agent emitted a `response.chart` / chart_spec event after consuming a
result set produced inside a subagent.

Usage:
  python run_agent.py --agent MASTER_AGENT_NAME --question "..." [--out trace.jsonl]
"""

import argparse
import json
import sys
from collections import Counter

import requests
import snowflake.connector
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def run(agent, question, database, schema, connection, out_path):
    conn = snowflake.connector.connect(connection_name=connection)
    try:
        token = conn.rest.token
        host = conn.host
        url = (
            f"https://{host}/api/v2/databases/{database}/schemas/{schema}"
            f"/agents/{agent}:run"
        )
        headers = {
            "Authorization": f'Snowflake Token="{token}"',
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }
        payload = {
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": question}]}
            ]
        }

        print(f"POST {url}")
        print(f"Q: {question}\n" + "=" * 78)
        resp = requests.post(
            url, headers=headers, json=payload, stream=True, verify=False
        )
        if resp.status_code != 200:
            print(f"HTTP {resp.status_code}\n{resp.text}")
            return 1

        event_counts = Counter()
        chart_specs = []
        tool_uses = []
        sql_seen = []
        text_chunks = []
        raw_lines = []

        cur_event = None
        for raw in resp.iter_lines(decode_unicode=True):
            if raw is None:
                continue
            raw_lines.append(raw)
            line = raw.strip()
            if line.startswith("event:"):
                cur_event = line[len("event:") :].strip()
                event_counts[cur_event] += 1
                continue
            if not line.startswith("data:"):
                continue
            body = line[len("data:") :].strip()
            if not body or body == "[DONE]":
                continue
            try:
                obj = json.loads(body)
            except json.JSONDecodeError:
                continue

            ev = cur_event or obj.get("event") or ""

            # ---- capture chart specs (the thing we care about) ----
            if "chart" in ev or "chart_spec" in body:
                spec = obj.get("chart_spec")
                if spec is None:
                    # may be nested under content/delta
                    for k in ("delta", "content", "data"):
                        node = obj.get(k)
                        if isinstance(node, dict) and "chart_spec" in node:
                            spec = node["chart_spec"]
                if spec is not None:
                    chart_specs.append(
                        {"event": ev, "tool_use_id": obj.get("tool_use_id"), "spec": spec}
                    )

            # ---- capture tool usage ----
            if "tool_use" in ev:
                tool_uses.append(obj)
            if "tool_result" in ev:
                s = json.dumps(obj)
                if "SELECT" in s.upper():
                    sql_seen.append(obj)

            if ev.endswith("text.delta") or ev.endswith("response.text.delta"):
                d = obj.get("text") or (obj.get("delta") or {}).get("text")
                if d:
                    text_chunks.append(d)

        if out_path:
            with open(out_path, "w") as f:
                f.write("\n".join(raw_lines))
            print(f"[raw stream written to {out_path}]\n")

        print("---- EVENT TYPE COUNTS ----")
        for k, v in event_counts.most_common():
            print(f"  {v:4d}  {k}")

        print("\n---- TOOL USE EVENTS ----")
        if not tool_uses:
            print("  (none captured)")
        for t in tool_uses:
            name = t.get("name") or (t.get("content") or {}).get("name")
            ttype = t.get("type") or (t.get("content") or {}).get("type")
            print(f"  name={name!r} type={ttype!r}")

        print("\n---- CHART SPECS EMITTED ----")
        if not chart_specs:
            print("  *** NONE — no chart was produced ***")
        for c in chart_specs:
            print(f"  event={c['event']} tool_use_id={c.get('tool_use_id')}")
            spec = c["spec"]
            if isinstance(spec, str):
                try:
                    spec = json.loads(spec)
                except json.JSONDecodeError:
                    pass
            print(json.dumps(spec, indent=2)[:2500])

        print("\n---- FINAL ANSWER TEXT ----")
        print("".join(text_chunks)[:4000] or "(no text captured)")

        return 0 if chart_specs else 2
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--database", default="SNOWFLAKE_INTELLIGENCE")
    ap.add_argument("--schema", default="AGENTS")
    ap.add_argument("--connection", default="demo")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    sys.exit(
        run(a.agent, a.question, a.database, a.schema, a.connection, a.out)
    )
