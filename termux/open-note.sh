#!/data/data/com.termux/files/usr/bin/bash
set -u

TERMUX_PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
TERMUX_HOME="${HOME:-/data/data/com.termux/files/home}"
export HOME="$TERMUX_HOME"
export PREFIX="$TERMUX_PREFIX"
export PATH="$TERMUX_PREFIX/bin:/system/bin:/system/xbin"

url="${1:-http://127.0.0.1:8083/}"
state_dir="${XDG_STATE_HOME:-$TERMUX_HOME/.local/state}/notes"
log_file="$state_dir/notification-actions.log"
mkdir -p "$state_dir"

{
  printf '%s tap %s\n' "$(date -Iseconds 2>/dev/null || date)" "$url"
  if [ -x "$TERMUX_PREFIX/bin/termux-open-url" ]; then
    "$TERMUX_PREFIX/bin/termux-open-url" "$url"
    status=$?
  else
    /system/bin/am start --user 0 -a android.intent.action.VIEW -d "$url"
    status=$?
  fi
  printf '%s result %s\n' "$(date -Iseconds 2>/dev/null || date)" "$status"
} >>"$log_file" 2>&1

exit "$status"
