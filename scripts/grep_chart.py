import re, sys

p = sys.argv[1]
raw = open(p).read()
for m in re.finditer(r"chart_spec", raw):
    s = max(0, m.start() - 400)
    print("=" * 70)
    print(raw[s : m.start() + 600])
