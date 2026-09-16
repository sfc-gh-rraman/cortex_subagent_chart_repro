"""Check whether INVENTORY schema is present in the master agent trace for a sales-only question."""
import json

base = "/Users/rraman/Documents/cortex_subagent_chart_repro/evidence/raw_streams"
path = f"{base}/01_top5_products.sse.txt"
raw = open(path).read()

# Check for inventory-specific identifiers in the stream
inventory_markers = ["INVENTORY_SV", "UNITS_ON_HAND", "UNITS_ON_ORDER", "REORDER_POINT",
                     "WAREHOUSE_CODE", "DC-CHICAGO", "DC-DALLAS", "query_inventory",
                     "STOCK_VALUE"]
sales_markers = ["SALES_SV", "NET_REVENUE", "ORDER_ID", "query_sales", "TOTAL_REVENUE"]

print("=== In MASTER trace (sales-only question) ===")
print("\nSales markers:")
for m in sales_markers:
    count = raw.upper().count(m.upper())
    print(f"  {m}: {count} occurrences")

print("\nInventory markers:")
for m in inventory_markers:
    count = raw.upper().count(m.upper())
    print(f"  {m}: {count} occurrences")

# Also check the initial tool_use events to see what tools were offered
bodies = []
for line in raw.split("\n"):
    if line.startswith("data:"):
        body = line[len("data:"):].strip()
        if body and body != "[DONE]":
            try:
                bodies.append(json.loads(body))
            except:
                pass

print("\n=== Tool use events ===")
for obj in bodies:
    s = json.dumps(obj)
    if '"tool_use"' in s[:100] or obj.get("type") == "tool_use":
        name = None
        for key_path in [["name"], ["tool_use", "name"], ["content", "name"]]:
            node = obj
            for k in key_path:
                if isinstance(node, dict):
                    node = node.get(k)
            if isinstance(node, str):
                name = node
                break
        if name:
            print(f"  tool_use: {name}")

# Count total chars that mention inventory concepts
inv_context_chars = 0
for line in raw.split("\n"):
    if any(m.upper() in line.upper() for m in ["INVENTORY", "WAREHOUSE", "ON_HAND", "ON_ORDER", "REORDER"]):
        inv_context_chars += len(line)
print(f"\nTotal chars in lines mentioning inventory concepts: {inv_context_chars:,}")
print(f"Total stream chars: {len(raw):,}")
print(f"Inventory share: {inv_context_chars/len(raw)*100:.1f}%")
