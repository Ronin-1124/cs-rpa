#!/usr/bin/env bash
set -euo pipefail
REPO="${RADXA_DOCS_DIR:-$HOME/.openclaw/workspace/knowledge/radxa-docs}"
LOG_DIR="${OPENCLAW_LOG_DIR:-$HOME/.openclaw/logs}"
LOG="$LOG_DIR/radxa-docs-sync.log"
REMOTE="${RADXA_DOCS_REMOTE:-https://github.com/radxa-docs/docs.git}"
BRANCH="${RADXA_DOCS_BRANCH:-main}"
OPENCLAW_BIN="${OPENCLAW_BIN:-$HOME/.nvm/versions/node/v24.18.0/bin/openclaw}"
export PATH="$HOME/.nvm/versions/node/v24.18.0/bin:/usr/bin:/bin"
mkdir -p "$LOG_DIR"
ts() { date -Iseconds; }
log() { echo "[$(ts)] $*" | tee -a "$LOG"; }

git_http() {
  git -c http.postBuffer=524288000 -c http.version=HTTP/1.1 "$@"
}

ensure_sparse() {
  git -C "$REPO" sparse-checkout set --cone docs i18n scripts .github
}

log "=== radxa-docs sync start ==="
if [[ ! -d "$REPO/.git" ]]; then
  log "clone missing; sparse-cloning $REMOTE -> $REPO"
  mkdir -p "$(dirname "$REPO")"
  git_http clone --depth 1 --filter=blob:none --sparse --branch "$BRANCH" "$REMOTE" "$REPO"
  ensure_sparse
else
  cd "$REPO"
  old="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
  log "fetch $REMOTE $BRANCH (was $old)"
  git remote set-url origin "$REMOTE"
  git_http fetch --depth 1 origin "$BRANCH"
  git checkout -B "$BRANCH" "origin/$BRANCH"
  git reset --hard "origin/$BRANCH"
  ensure_sparse
  new="$(git rev-parse --short HEAD)"
  log "now $new"
fi

cd "$REPO"
if [[ -f .gitmodules ]]; then
  log "submodule update (depth 1)"
  git_http submodule update --init --recursive --depth 1 || log "WARN submodule update failed (continuing)"
fi

head_full="$(git -C "$REPO" rev-parse HEAD)"
date_full="$(git -C "$REPO" log -1 --format='%ci %s')"
md_count="$(find "$REPO/docs" -type f \( -name '*.md' -o -name '*.mdx' \) 2>/dev/null | wc -l | tr -d ' ')"
meta="$HOME/.openclaw/workspace/knowledge/radxa-docs-status.md"
cat > "$meta" <<EOF
# radxa-docs mirror status

- remote: $REMOTE
- branch: $BRANCH
- commit: \`$head_full\`
- last upstream: $date_full
- last sync: $(ts)
- chinese docs markdown files: $md_count
- path: \`knowledge/radxa-docs/\`
- checkout: sparse (docs, i18n, scripts, .github)

Official product docs live under \`knowledge/radxa-docs/docs/\` (Chinese)
and \`knowledge/radxa-docs/i18n/en/docusaurus-plugin-content-docs/current/\` (English).
Shop policy stays in \`knowledge/shop-faq.md\`.
EOF
log "wrote status file; chinese markdown count=$md_count"

if [[ -x "$OPENCLAW_BIN" ]] || command -v openclaw >/dev/null 2>&1; then
  log "reindex openclaw memory"
  "${OPENCLAW_BIN:-openclaw}" memory index --agent main >>"$LOG" 2>&1 || log "WARN memory index failed"
else
  log "WARN openclaw not on PATH; skip index"
fi
log "=== radxa-docs sync done ==="
