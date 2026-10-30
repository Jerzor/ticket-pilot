#!/usr/bin/env bash
# Zero tokens: is the issue tracker reachable (VPN)? Exit 0 = OK, 1 = unreachable or 403; the reason goes to stdout.
source "$(dirname "$0")/common.sh"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$(cfg .tracker.url)$(cfg .tracker.healthPath)")
case "$code" in
  2??|3??) exit 0 ;;
  403) echo "tracker 403 - no VPN"; exit 1 ;;
  000) echo "tracker unreachable - no network/VPN"; exit 1 ;;
  *) echo "tracker answers $code"; exit 1 ;;
esac
