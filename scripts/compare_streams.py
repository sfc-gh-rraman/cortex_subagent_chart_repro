"""
Compare master-with-toolset vs subagent-direct:
  - raw stream bytes (proxy for total tokens)
  - number of tool_use / tool_result events
  - size of semantic model context payloads (the main token cost driver)
"""
import json, sys, os

def analyze(path, label):
    raw = open(path).read()
    lines = raw.strip().split("\n")

    # count events
    events = {}
    data_bodies = []
    for line in lines:
        if line.startswith("event:"):
            ev = line[len("event:"):].strip()
            events[ev] = events.get(ev, 0) + 1
        elif line.startswith("data:"):
            body = line[len("data:"):].strip()
            if body and body != "[DONE]":
                try:
                    data_bodies.append(json.loads(body))
                except:
                    pass

    # find semantic context payloads (these contain the full semantic view schema)
    sem_sizes = []
    tool_result_sizes = []
    for obj in data_bodies:
        s = json.dumps(obj)
        if "semantic" in s.lower() and ("tables" in s or "dimensions" in s or "metrics" in s):
            sem_sizes.append(len(s))
        # tool_result bodies carry the SQL result sets
        if "tool_result" in s[:200].lower() or "result" in str(obj.get("type","")):
            tool_result_sizes.append(len(s))

    total_data_chars = sum(len(json.dumps(b)) for b in data_bodies)

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  File: {os.path.basename(path)} ({os.path.getsize(path):,} bytes)")
    print(f"{'='*60}")
    print(f"  SSE lines:              {len(lines):,}")
    print(f"  Parsed data payloads:   {len(data_bodies):,}")
    print(f"  Total data chars:       {total_data_chars:,}")
    print(f"  Event types:")
    for k, v in sorted(events.items(), key=lambda x: -x[1]):
        print(f"    {v:4d}  {k}")
    print(f"  Semantic context payloads: {len(sem_sizes)}")
    for i, s in enumerate(sem_sizes):
        print(f"    payload {i}: {s:,} chars")
    print(f"  Total semantic chars:   {sum(sem_sizes):,}")
    print(f"  Tool result payloads:   {len(tool_result_sizes)}")
    for i, s in enumerate(tool_result_sizes):
        print(f"    result {i}: {s:,} chars")

    return {
        "label": label,
        "stream_bytes": os.path.getsize(path),
        "total_data_chars": total_data_chars,
        "semantic_chars": sum(sem_sizes),
        "n_events": sum(events.values()),
    }


base = "/Users/rraman/Documents/cortex_subagent_chart_repro/evidence/raw_streams"

master = analyze(f"{base}/01_top5_products.sse.txt", "MASTER AGENT (toolset flattened)")
sub = analyze(f"{base}/05_subagent_direct.sse.txt", "SUBAGENT (direct, same question)")

print(f"\n{'='*60}")
print("  COMPARISON")
print(f"{'='*60}")
print(f"  Stream bytes: master={master['stream_bytes']:,}  sub={sub['stream_bytes']:,}  ratio={master['stream_bytes']/max(sub['stream_bytes'],1):.2f}x")
print(f"  Data chars:   master={master['total_data_chars']:,}  sub={sub['total_data_chars']:,}  ratio={master['total_data_chars']/max(sub['total_data_chars'],1):.2f}x")
print(f"  Semantic:     master={master['semantic_chars']:,}  sub={sub['semantic_chars']:,}  ratio={master['semantic_chars']/max(sub['semantic_chars'],1):.2f}x")
