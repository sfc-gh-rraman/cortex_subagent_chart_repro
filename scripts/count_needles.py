import sys

p = sys.argv[1]
raw = open(p).read()
out = []
out.append("BYTES: %d" % len(raw))
for needle in ["chart_spec", "chart", "vega", "data_to_chart", "response.chart"]:
    out.append("%-16s count=%d" % (needle, raw.count(needle)))
open(sys.argv[2], "w").write("\n".join(out) + "\n")
