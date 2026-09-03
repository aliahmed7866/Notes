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
