#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
APP_DIR="${NOTES_APP_DIR:-$HOME/Notes}"
SERVICE="$PREFIX/var/service/notes-deploy"
mkdir -p "$SERVICE"
cat > "$SERVICE/run" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec 2>&1
cd "$APP_DIR"
exec bash "$APP_DIR/termux/auto-deploy.sh"
EOF
chmod +x "$SERVICE/run"
sv-enable notes-deploy >/dev/null 2>&1 || true
for _ in $(seq 1 30); do
  [ -e "$SERVICE/supervise/ok" ] && break
  sleep 0.5
done
if [ ! -e "$SERVICE/supervise/ok" ]; then
  echo "[Notes] runit did not supervise notes-deploy. Ensure Termux:Services is running, then rerun this installer." >&2
  exit 1
fi
sv up notes-deploy
echo "[Notes] Auto-deploy enabled."
