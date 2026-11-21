#!/usr/bin/env bash
# Run one Devin worker on one task, confined to its own folder.
#   usage: scripts/devin-run.sh <frontend|backend|voice|review> <task-file.md>
# Prints the worker's final message, then a domain check of every file changed during the run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ROLE="${1:?role: frontend|backend|voice|review}"
TASK="${2:?path to task markdown file}"
[ -f "$TASK" ] || { echo "task file not found: $TASK" >&2; exit 2; }

case "$ROLE" in
  frontend|backend|voice) DIR="$ROLE" ;;
  review) DIR="reviews" ;;
  *) echo "unknown role: $ROLE" >&2; exit 2 ;;
esac

# shellcheck disable=SC1091
source "$ROOT/.devin/roles/models.env"
MODEL_VAR="$(echo "$ROLE" | tr a-z A-Z)_MODEL"
MODEL="${DEVIN_ROLE_MODEL:-${!MODEL_VAR}}"   # DEVIN_ROLE_MODEL overrides, e.g. for cheap smoke tests

TS="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$ROOT/logs"
PROMPT="$ROOT/logs/$ROLE-$TS.prompt.md"
LOG="$ROOT/logs/$ROLE-$TS.log"
{
  cat "$ROOT/.devin/roles/shared.md"; echo
  cat "$ROOT/.devin/roles/$ROLE.md"; echo
  echo "# Task"; cat "$TASK"
} > "$PROMPT"

# Fingerprint every project file (path + content hash) so any create/modify/delete is detected.
snapshot() {
  (cd "$ROOT" && find . -path ./.git -prune -o -path ./logs -prune -o -name node_modules -prune \
     -o -name .venv -prune -o -name __pycache__ -prune -o -type f -print0 | sort -z | xargs -0 sha1sum)
}
before="$(snapshot)"

echo ">> devin role=$ROLE model=$MODEL dir=$DIR log=${LOG#$ROOT/}" >&2
set +e
( cd "$ROOT/$DIR" && devin -p \
    --model "$MODEL" \
    --config "$ROOT/.devin/roles/$ROLE.json" \
    --sandbox \
    --respect-workspace-trust false \
    --prompt-file "$PROMPT" ) 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}
set -e

# Domain check: anything that changed during this run must be inside $DIR/.
after="$(snapshot)"
changed="$(diff <(echo "$before") <(echo "$after") | grep -E '^[<>]' | awk '{print $3}' | sed 's|^\./||' | sort -u || true)"
# Workers running in parallel change their own folders during our run: those are not our violations.
# A role counts as concurrent if its log was written after our prompt file was created.
concurrent=""
for r in frontend backend voice review; do
  [ "$r" = "$ROLE" ] && continue
  if find "$ROOT/logs" -name "$r-*.log" -newer "$PROMPT" 2>/dev/null | grep -q .; then
    case "$r" in review) concurrent+=" reviews" ;; *) concurrent+=" $r" ;; esac
  fi
done
# Devin's sandbox creates and removes empty placeholder dotfiles in worker folders; ignore those names.
excl=(-e "^$DIR/" -e '^$' -e '^logs/' -E -e '^[a-z]+/(\.bash_profile|\.bashrc|\.gitconfig|\.gitmodules|\.idea|\.mcp\.json|mcp\.json|\.profile|\.ripgreprc|\.vscode|\.zprofile|\.zshrc|\.claude/.*)$')
for d in $concurrent; do excl+=(-e "^$d/"); done
violations="$(echo "$changed" | grep -v "${excl[@]}" || true)"
[ -n "$concurrent" ] && echo "(note: ran alongside:$concurrent — their folders were excluded from this check)"

echo
echo "== files changed by $ROLE =="
echo "${changed:-(none)}"
if [ -n "$violations" ]; then
  echo "!! DOMAIN VIOLATION: $ROLE changed files outside $DIR/:"
  echo "$violations"
  exit 3
fi
exit "$status"
