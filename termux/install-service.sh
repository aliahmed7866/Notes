#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
APP_DIR="${NOTES_APP_DIR:-$HOME/Notes}"
PORT="${NOTES_PORT:-8083}"
CONFIG_DIR="${NOTES_CONFIG_DIR:-$HOME/.config/notes}"
ENV_FILE="$CONFIG_DIR/env"
VENV="$APP_DIR/.venv"
WEB_SERVICE="$PREFIX/var/service/notes"
REMINDER_SERVICE="$PREFIX/var/service/notes-reminders"
AYCF_REGISTRY="${AYCF_ADMIN_REGISTRY:-$HOME/.config/aycf/apps.json}"

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
"$VENV/bin/python" "$APP_DIR/termux/register-admin.py" "$AYCF_REGISTRY" "$PORT"
wait_for_supervision() {
  service_name="$1"
  service_dir="$PREFIX/var/service/$service_name"
  for _ in $(seq 1 30); do
    [ -e "$service_dir/supervise/ok" ] && return 0
    sleep 0.5
  done
  echo "[Notes] runit did not supervise $service_name. Ensure Termux:Services is running, then rerun this installer." >&2
  return 1
}

start_service() {
  service_name="$1"
  sv-enable "$service_name" >/dev/null 2>&1 || true
  wait_for_supervision "$service_name"
  sv up "$service_name"
}

start_service notes
start_service notes-reminders

for _ in $(seq 1 20); do
  if curl -fsS --max-time 3 "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "[Notes] Ready at http://127.0.0.1:$PORT"
    exit 0
  fi
  sleep 0.5
done
echo "[Notes] Web service started but its health check failed." >&2
sv status notes || true
exit 1
