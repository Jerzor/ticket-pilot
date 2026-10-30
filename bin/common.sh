# Sourced by every script: paths and config (config.json in the repo root, read with jq).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="${TICKET_PILOT_CONFIG:-$ROOT/config.json}"
[ -f "$CONFIG" ] || CONFIG="$ROOT/config.example.json"
cfg() { jq -r "$1 // empty" "$CONFIG"; }
expand() { echo "${1/#\~/$HOME}"; }
DATA="$(expand "${TICKET_PILOT_DATA:-$(cfg .dataDir)}")"
mkdir -p "$DATA"
CLAUDE="$(expand "$(cfg .claude.bin)")"
export DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$(id -u)/bus"   # notify-send from cron
# cron does not load the shell profile -> node/npm from nvm (newest installed version)
NODE_BIN=$(ls -d "$HOME"/.nvm/versions/node/v*/bin 2>/dev/null | sort -V | tail -1 || true)
if [ -n "$NODE_BIN" ]; then export PATH="$NODE_BIN:$PATH"; fi
