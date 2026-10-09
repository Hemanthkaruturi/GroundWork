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

# D. an existing repo with specs written by another tool (spec-kit style) -> import, classify
mkdir -p "$SB/d-legacy-specs/specs/001-search/" "$SB/d-legacy-specs/specs/002-export/" "$SB/d-legacy-specs/.specify" "$SB/d-legacy-specs/src"; g "$SB/d-legacy-specs"
cp "$SB/b-legacy-repo/src/app.py" "$SB/d-legacy-specs/src/app.py"
spec() { cat > "$1" <<SPEC
# Spec: $2

**ID:** $3
**Status:** $4
**Owner:** —
**Created:** 2026-08-12

## 1. Problem
$5

## 2. Users and context
- An operator.

## 3. User stories
- **US-1**: As an operator, I want $2, so that I can see results.

## 4. Functional requirements
- **FR-1**: $6

## 5. Non-functional requirements
- **NFR-1**: Responds within a second.

## 6. Acceptance criteria
- **AC-1**: Given the service runs, when I call it, then $6 (covers FR-1)

## 7. Out of scope
Everything else.

## 8. Resolved decisions
None.

## 9. Open questions
None.

## 10. Constitution check
Complies.
SPEC
}
spec "$SB/d-legacy-specs/specs/001-search/spec.md" "Search" 001-search Approved "Nobody can find anything." "GET / returns hello."
spec "$SB/d-legacy-specs/specs/002-export/spec.md" "Export" 002-export Draft "Results cannot be exported." "GET /export returns a CSV."
printf -- '- [x] **T001** — serve hello\n  - **Files:** src/app.py\n  - **Done when:** curl works\n  - **Covers:** FR-1\n' > "$SB/d-legacy-specs/specs/001-search/tasks.md"
printf -- '- [ ] **T001** — write the CSV\n  - **Files:** src/app.py\n  - **Done when:** curl /export works\n  - **Covers:** FR-1\n' > "$SB/d-legacy-specs/specs/002-export/tasks.md"

cat <<MSG
Sandbox ready in $SB
  a-empty/        -> expect level UNKNOWN
  b-legacy-repo/  -> expect level STANDALONE, foundation docs missing
  c-shop/         -> expect level WORKSPACE (repos: shop-api, shop-web)
  d-legacy-specs/ -> expect level STANDALONE with two spec-kit style specs to import (adopt-specs)
Start Claude in one with the plugin loaded, e.g.:
  cd $SB/c-shop && claude --plugin-dir $(cd "$(dirname "$0")/.." && pwd)/plugins/groundwork-specflow
See docs/manual-testing.md for the full script.
MSG
