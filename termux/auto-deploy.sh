#!/data/data/com.termux/files/usr/bin/bash
set -u
APP_DIR="${NOTES_APP_DIR:-$HOME/Notes}"
BRANCH="${NOTES_BRANCH:-main}"
INTERVAL="${NOTES_DEPLOY_INTERVAL:-60}"
while true; do
  cd "$APP_DIR" || exit 1
  if [ -z "$(git status --porcelain --untracked-files=no 2>/dev/null)" ]; then
    remote="$(git ls-remote origin "refs/heads/$BRANCH" 2>/dev/null | awk 'NR==1{print $1}')"
    local="$(git rev-parse HEAD 2>/dev/null || true)"
    if [ -n "$remote" ] && [ "$remote" != "$local" ]; then
      git fetch --quiet origin "$BRANCH" && git checkout --quiet "$BRANCH" && git merge --ff-only --quiet "origin/$BRANCH" && bash termux/install-service.sh
    fi
  fi
  sleep "$INTERVAL"
done
