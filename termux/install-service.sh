#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
APP_DIR="${NOTES_APP_DIR:-$HOME/Notes}"
PORT="${NOTES_PORT:-8083}"
CONFIG_DIR="${NOTES_CONFIG_DIR:-$HOME/.config/notes}"
ENV_FILE="$CONFIG_DIR/env"
VENV="$APP_DIR/.venv"
WEB_SERVICE="$PREFIX/var/service/notes"
REMINDER_SERVICE="$PREFIX/var/service/notes-reminders"

cd "$APP_DIR"
command -v sv >/dev/null 2>&1 || pkg install -y termux-services
pkg install -y termux-api >/dev/null 2>&1 || true
[ -d "$VENV" ] || python -m venv "$VENV"
"$VENV/bin/python" -m pip install -q -r requirements.txt
mkdir -p "$CONFIG_DIR" "$WEB_SERVICE" "$REMINDER_SERVICE"
chmod 700 "$CONFIG_DIR"
if [ ! -f "$ENV_FILE" ]; then
  SECRET="$("$VENV/bin/python" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  printf "export NOTES_SECRET_KEY='%s'\nexport NOTES_BIND_HOST='127.0.0.1'\nexport NOTES_PORT='%s'\nexport NOTES_TIMEZONE='Europe/London'\n" "$SECRET" "$PORT" > "$ENV_FILE"
  chmod 600 "$ENV_FILE"
fi
cat > "$WEB_SERVICE/run" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec 2>&1
cd "$APP_DIR"
. "$ENV_FILE"
exec "$VENV/bin/python" termux/run-web.py
EOF
cat > "$REMINDER_SERVICE/run" <<EOF
#!/data/data/com.termux/files/usr/bin/bash
exec 2>&1
cd "$APP_DIR"
. "$ENV_FILE"
exec "$VENV/bin/python" reminder_worker.py
EOF
chmod +x "$WEB_SERVICE/run" "$REMINDER_SERVICE/run"
sv-enable notes >/dev/null 2>&1 || true
sv-enable notes-reminders >/dev/null 2>&1 || true
sv restart notes >/dev/null 2>&1 || sv up notes
sv restart notes-reminders >/dev/null 2>&1 || sv up notes-reminders
echo "[Notes] Ready at http://127.0.0.1:$PORT"
