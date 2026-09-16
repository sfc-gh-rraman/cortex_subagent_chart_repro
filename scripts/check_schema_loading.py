"""
Count how big the flattened semantic model context is in the master agent's trace
when it has 2 semantic views (via toolset) vs what a focused single-view agent would see.

The question: does the master agent load ALL semantic view schemas from the toolset,
even for a question that only needs one?
"""
import json, re

base = "/Users/rraman/Documents/cortex_subagent_chart_repro/evidence/raw_streams"
path = f"{base}/01_top5_products.sse.txt"
raw = open(path).read()

# Extract all data bodies
bodies = []
for line in raw.split("\n"):
    if line.startswith("data:"):
        body = line[len("data:"):].strip()
        if body and body != "[DONE]":
            try:
                bodies.append(json.loads(body))
            except:
                pass

# Find the semantic context / pruned_note payloads — these show what schemas got loaded
sem_payloads = []
for i, obj in enumerate(bodies):
    s = json.dumps(obj)
    if "pruned_note" in s or ("tables" in s and "dimensions" in s):
        sem_payloads.append((i, len(s), s[:300]))

print("Semantic context payloads in MASTER trace:")
print(f"  Count: {len(sem_payloads)}")
for idx, size, preview in sem_payloads:
    # Check which semantic view this belongs to
    if "SALES" in preview.upper() and "INVENTORY" not in preview.upper():
        view = "SALES_SV only"
    elif "INVENTORY" in preview.upper() and "SALES" not in preview.upper():
        view = "INVENTORY_SV only"
    elif "SALES" in preview.upper() and "INVENTORY" in preview.upper():
        view = "BOTH views"
    else:
        view = "unknown"
    print(f"  payload[{idx}]: {size:,} chars  ({view})")
    print(f"    preview: {preview[:200]}...")

total = sum(s for _, s, _ in sem_payloads)
print(f"\nTotal semantic context: {total:,} chars")
print(f"\nIf only SALES_SV was loaded (single-view agent), it would be ~{sem_payloads[0][1]:,} chars")
print(f"Overhead from flattening both views: {total - sem_payloads[0][1]:,} chars ({(total - sem_payloads[0][1])/total*100:.0f}% of total semantic context)")
