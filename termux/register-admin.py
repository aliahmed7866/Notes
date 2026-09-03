from __future__ import annotations

import json
import os
import sys
from pathlib import Path

registry=Path(sys.argv[1]).expanduser()
port=int(sys.argv[2])
root=Path(os.environ.get("NOTES_APP_DIR",Path.home()/"Notes")).expanduser()
entry={
    "id":"notes",
    "name":"Notes",
    "description":"Private notes, search and Android reminders",
    "working_dir":str(root),
    "service":"notes",
    "port":port,
    "health_url":f"http://127.0.0.1:{port}/health",
    "open_url":f"http://127.0.0.1:{port}",
    "process_match":f"{root}/.venv/bin/python termux/run-web.py",
}
try:
    payload=json.loads(registry.read_text(encoding="utf-8")) if registry.exists() else {"apps":[]}
except (OSError,json.JSONDecodeError):
    payload={"apps":[]}
apps=[item for item in payload.get("apps",[]) if isinstance(item,dict) and item.get("id")!="notes"]
apps.append(entry)
registry.parent.mkdir(parents=True,exist_ok=True)
registry.write_text(json.dumps({"apps":apps},indent=2)+"\n",encoding="utf-8")
registry.chmod(0o600)
