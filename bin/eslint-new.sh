#!/usr/bin/env bash
# Only NEW ESLint errors vs origin/main (legacy repos have hundreds of old ones): eslint-new.sh <worktree> [file.ts …]
# Without files: the .ts files changed in origin/main...HEAD.
set -uo pipefail
source "$(dirname "$0")/common.sh"
W="$1"; shift
cd "$W" || exit 2
FILES=("$@")
[ ${#FILES[@]} -eq 0 ] && mapfile -t FILES < <(git diff --name-only --diff-filter=AM origin/main...HEAD -- '*.ts')
norm() { sed -E 's/^[^:]*:[0-9]+:[0-9]+: //' | sort; }   # drop line numbers - compare the messages only
new=0
for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  now=$(npx eslint -f unix "$f" 2>/dev/null | grep -E '^[^:]+:[0-9]+:[0-9]+:' | norm)
  old=$(git show "origin/main:$f" 2>/dev/null | npx eslint -f unix --stdin --stdin-filename "$f" 2>/dev/null | grep -E '^[^:]+:[0-9]+:[0-9]+:' | norm)
  added=$(comm -23 <(echo "$now") <(echo "$old") | grep -v '^$')
  if [ -n "$added" ]; then new=1; echo "== $f"; echo "$added"; fi
done
[ $new -eq 0 ] && echo "ESLINT_OK: no new errors (${#FILES[@]} files)" || { echo "ESLINT_NEW_ERRORS"; exit 1; }
