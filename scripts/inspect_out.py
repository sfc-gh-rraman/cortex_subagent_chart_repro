import json, re, sys

p = sys.argv[1]
raw = open(p).read()
print("BYTES:", len(raw))
print("has chart_spec:", "chart_spec" in raw)
print("content types found:", sorted(set(re.findall(r'"type"\s*:\s*"([a-z_]+)"', raw))))
print("---- first 1200 chars ----")
print(raw[:1200])
