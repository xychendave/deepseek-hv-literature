"""Smoke-test the real stdio process without printing private paper contents."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
requests = [
    {"jsonrpc":"2.0", "id":1, "method":"initialize", "params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"hv-smoke","version":"1.0"}}},
    {"jsonrpc":"2.0", "method":"notifications/initialized"},
    {"jsonrpc":"2.0", "id":2, "method":"tools/list"},
    {"jsonrpc":"2.0", "id":3, "method":"tools/call", "params":{"name":"library_status","arguments":{}}},
]
result = subprocess.run([sys.executable, str(ROOT/"hv_literature.py"), "mcp"],
                        input="\n".join(json.dumps(r) for r in requests)+"\n",
                        capture_output=True, text=True, timeout=30)
if result.returncode:
    raise SystemExit("MCP process failed; check initialization and dependencies.")
responses = {r["id"]:r for r in map(json.loads, result.stdout.splitlines())}
assert responses[1]["result"]["serverInfo"]["name"] == "hv-literature"
names = {t["name"] for t in responses[2]["result"]["tools"]}
assert names == {"library_status","search_passages","read_page","sync_library","daily_digest"}
assert not responses[3]["result"]["isError"]
status = json.loads(responses[3]["result"]["content"][0]["text"])
print(json.dumps({"ok":True,"tools":sorted(names),"counts":status["counts"]}, ensure_ascii=False, indent=2))
