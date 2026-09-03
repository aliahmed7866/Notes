from datetime import datetime, timedelta, timezone

import reminder_worker
import store

def test_worker_notifies_due_items_once(tmp_path,monkeypatch):
    monkeypatch.setattr(store,"DB_PATH",tmp_path/"notes.sqlite3")
    note=store.save_note(None,"Pay bill","Before Friday","","slate")
    store.set_reminder(note,(datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat(),"none")
    sent=[]
    monkeypatch.setattr(reminder_worker,"notify",lambda item: sent.append(item) or True)
    assert reminder_worker.run_once()==1
    assert reminder_worker.run_once()==0
    assert sent[0]["title"]=="Pay bill"

def test_completing_recurring_reminder_creates_next_occurrence(tmp_path,monkeypatch):
    monkeypatch.setattr(store,"DB_PATH",tmp_path/"notes.sqlite3")
    note=store.save_note(None,"Weekly review","","","slate")
    due=(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()
    store.set_reminder(note,due,"weekly")
    current=store.get_note(note)["reminder"]
    store.reminder_action(current["id"],"done")
    next_item=store.get_note(note)["reminder"]
    assert next_item is not None
    assert next_item["id"] != current["id"]
    assert datetime.fromisoformat(next_item["due_at"]) > datetime.now(timezone.utc)

def test_notification_tap_opens_exact_note(monkeypatch):
    commands = []
    monkeypatch.setattr(
        reminder_worker.shutil,
        "which",
        lambda name: f"/data/data/com.termux/files/usr/bin/{name}",
    )
    class Result:
        returncode = 0
    monkeypatch.setattr(
        reminder_worker.subprocess,
        "run",
        lambda command, **kwargs: commands.append(command) or Result(),
    )
    assert reminder_worker.notify({
        "id": 17,
        "note_id": 42,
        "title": "Pay bill",
        "body": "Before Friday",
    })
    command = commands[0]
    assert command[0].endswith("/termux-notification")
    action = command[command.index("--action") + 1]
    assert "/notes/42/edit?show=reminder#reminder" in action
    assert action.startswith("/data/data/com.termux/files/usr/bin/termux-open-url ")
