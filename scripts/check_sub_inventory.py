"""Same inventory-leakage check but on the subagent-direct trace."""
base = "/Users/rraman/Documents/cortex_subagent_chart_repro/evidence/raw_streams"
path = f"{base}/05_subagent_direct.sse.txt"
raw = open(path).read()

inventory_markers = ["INVENTORY_SV", "UNITS_ON_HAND", "UNITS_ON_ORDER", "REORDER_POINT",
                     "WAREHOUSE_CODE", "DC-CHICAGO", "query_inventory", "STOCK_VALUE"]

print("=== In SUBAGENT-DIRECT trace (sales-only question) ===")
print("\nInventory markers:")
for m in inventory_markers:
    count = raw.upper().count(m.upper())
    print(f"  {m}: {count} occurrences")

inv_context_chars = 0
for line in raw.split("\n"):
    if any(m.upper() in line.upper() for m in ["INVENTORY", "WAREHOUSE", "ON_HAND", "ON_ORDER", "REORDER"]):
        inv_context_chars += len(line)
print(f"\nTotal chars in inventory lines: {inv_context_chars:,}")
print(f"Total stream chars: {len(raw):,}")
print(f"Inventory share: {inv_context_chars/len(raw)*100:.1f}%")
