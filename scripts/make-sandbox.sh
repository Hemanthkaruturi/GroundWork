#!/usr/bin/env bash
# Build throwaway directories for manually testing groundwork. Safe to re-run (wipes the sandbox).
set -euo pipefail
SB="${1:-$HOME/groundwork-sandbox}"
case "$SB" in ""|/|"$HOME") echo "refusing to use '$SB'"; exit 1;; esac
rm -rf "$SB"; mkdir -p "$SB"
g() { git -C "$1" init -q; git -C "$1" config user.email you@example.com; git -C "$1" config user.name You; }

# A. nothing at all -> level UNKNOWN
mkdir "$SB/a-empty"

# B. an existing repo with code but no docs -> STANDALONE, brownfield bootstrap
mkdir -p "$SB/b-legacy-repo/src"; g "$SB/b-legacy-repo"
cat > "$SB/b-legacy-repo/src/app.py" <<'PY'
from http.server import BaseHTTPRequestHandler, HTTPServer
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"hello")
if __name__ == "__main__":
    HTTPServer(("", 8000), H).serve_forever()
PY
printf 'flask\n' > "$SB/b-legacy-repo/requirements.txt"

# C. a workspace holding two repos -> WORKSPACE (and each repo is REPO once PROJECT.md exists)
mkdir -p "$SB/c-shop"; mkdir "$SB/c-shop/shop-api" "$SB/c-shop/shop-web"
g "$SB/c-shop/shop-api"; g "$SB/c-shop/shop-web"

cat <<MSG
Sandbox ready in $SB
  a-empty/        -> expect level UNKNOWN
  b-legacy-repo/  -> expect level STANDALONE, foundation docs missing
  c-shop/         -> expect level WORKSPACE (repos: shop-api, shop-web)
Start Claude in one with the plugin loaded, e.g.:
  cd $SB/c-shop && claude --plugin-dir $(cd "$(dirname "$0")/.." && pwd)/plugins/groundwork
See docs/manual-testing.md for the full script.
MSG
