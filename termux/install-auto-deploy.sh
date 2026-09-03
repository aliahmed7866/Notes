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
sv restart notes-deploy >/dev/null 2>&1 || sv up notes-deploy >/dev/null 2>&1 || true
echo "[Notes] Auto-deploy enabled."
