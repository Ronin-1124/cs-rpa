from pathlib import Path

p = Path("/home/radxa/.openclaw/workspace/AGENTS.md")
t = p.read_text(encoding="utf-8")
old = "4. Prefer `memory_search` when looking up a product name or error string, then `memory_get` / read the matching markdown file."
new = (
    "4. Look up products by searching files under `knowledge/radxa-docs/docs/` "
    "(grep/rg for the product name or error string), then read the matching markdown. "
    "`memory_search` needs an embedding provider and is not configured on this host yet."
)
if old not in t:
    raise SystemExit("pattern not found")
p.write_text(t.replace(old, new), encoding="utf-8")
print("updated AGENTS.md")
