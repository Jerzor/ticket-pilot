#!/usr/bin/env bash
# Rebuilds the GitHub Pages demo (docs/index.html) and its screenshot from demo/data. Run after changing the dashboard.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/web/dashboard.py" --demo > /dev/null
cp "$ROOT/demo/dashboard.html" "$ROOT/docs/index.html"
touch "$ROOT/docs/.nojekyll"
CHROME=$(command -v google-chrome || command -v chromium || echo "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
if [ -x "$CHROME" ]; then
  PROFILE=$(mktemp -d)
  "$CHROME" --headless=new --user-data-dir="$PROFILE" --disable-gpu --hide-scrollbars --window-size=1280,1700 \
    --screenshot="$ROOT/docs/dashboard.png" "file://$ROOT/demo/dashboard.html" 2>/dev/null
  rm -rf "$PROFILE"
fi
echo "docs/index.html ready"
