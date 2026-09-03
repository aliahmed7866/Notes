from __future__ import annotations

import os
import shutil
import subprocess
import time
from datetime import datetime, timezone

import store

INTERVAL=max(20,int(os.environ.get("NOTES_REMINDER_INTERVAL","60")))
OPEN_URL=os.environ.get("NOTES_OPEN_URL","http://127.0.0.1:8083")

def notify(item: dict) -> bool:
    title=item["title"] or "Notes reminder"
    body=(item["body"] or "Reminder due").replace("\n"," ")[:180]
    if shutil.which("termux-notification"):
        proc=subprocess.run([
            "termux-notification","--id",f"notes-{item['id']}",
            "--title",title,"--content",body,"--priority","default",
            "--action",f"termux-open-url {OPEN_URL}",
        ],capture_output=True,text=True,timeout=15,check=False)
        return proc.returncode==0
    print(f"[Notes reminder] {title}: {body}",flush=True)
    return True

def run_once() -> int:
    count=0
    for item in store.due_reminders(datetime.now(timezone.utc).isoformat(timespec="seconds")):
        if notify(item):
            store.mark_notified(item["id"]); count+=1
    return count

if __name__=="__main__":
    while True:
        try: run_once()
        except Exception as exc: print(f"[Notes reminder] {type(exc).__name__}: {exc}",flush=True)
        time.sleep(INTERVAL)
