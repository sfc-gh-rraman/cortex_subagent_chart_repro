"""Compare token usage: master agent (with flattened toolset) vs subagent alone."""
import json, re, sys

def extract_tokens(path):
    raw = open(path).read()
    # Look for usage/token info in the SSE stream
    tokens = {}
    for line in raw.split("\n"):
        if not line.startswith("data:"):
            continue
        body = line[len("data:"):].strip()
        if not body or body == "[DONE]":
            continue
        try:
            obj = json.loads(body)
        except:
            continue
        # Check for usage info
        if "usage" in obj:
            tokens["usage"] = obj["usage"]
        if "token" in json.dumps(obj).lower():
            for k in ("input_tokens", "output_tokens", "total_tokens",
                       "prompt_tokens", "completion_tokens"):
                if k in obj:
                    tokens[k] = obj[k]
            # nested under usage
            if isinstance(obj.get("usage"), dict):
                for k, v in obj["usage"].items():
                    tokens[k] = v
    return tokens

for label, path in [
    ("MASTER (toolset flattened)", sys.argv[1]),
    ("SUBAGENT (direct)",          sys.argv[2]),
]:
    t = extract_tokens(path)
    print(f"\n{label}")
    print(f"  File: {path}")
    if t:
        for k, v in sorted(t.items()):
            print(f"  {k}: {v}")
    else:
        print("  (no token usage found in stream)")
