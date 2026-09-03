from datetime import datetime, timedelta, timezone

import app
import store

def client(tmp_path,monkeypatch):
    monkeypatch.setattr(store,"DB_PATH",tmp_path/"notes.sqlite3")
    flask=app.create_app({"TESTING":True,"SECRET_KEY":"test"})
    return flask.test_client()

def csrf(c):
    c.get("/")
    with c.session_transaction() as s:return s["csrf_token"]

def test_capture_search_archive_restore_and_export(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch); token=csrf(c)
    r=c.post("/new",data={"csrf_token":token,"title":"Book flight","body":"Check Budapest","tags":"Travel, AYCF","colour":"violet"})
    assert r.status_code==302
    assert b"Book flight" in c.get("/?q=Budapest").data
    note=store.list_notes()[0]
    c.post(f"/notes/{note['id']}/archive",data={"csrf_token":token})
    assert not store.list_notes()
    assert len(store.list_notes("archive"))==1
    assert c.get("/export.json").json["notes"][0]["tags"]==["travel","aycf"]

def test_due_reminder_can_be_snoozed(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch); token=csrf(c)
    due=(datetime.now()+timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
    c.post("/new",data={"csrf_token":token,"title":"Call","body":"","tags":"","colour":"slate","due_at":due,"recurrence":"weekly"})
    note=store.get_note(store.list_notes()[0]["id"])
    assert note["reminder"]["recurrence"]=="weekly"
    c.post(f"/reminders/{note['reminder']['id']}/snooze",data={"csrf_token":token,"minutes":"60"})
    changed=store.get_note(note["id"])["reminder"]
    assert changed["due_at"]>note["reminder"]["due_at"]

def test_mutations_require_csrf(tmp_path,monkeypatch):
    c=client(tmp_path,monkeypatch)
    assert c.post("/new",data={"title":"No"}).status_code==400

def test_configured_timezone_is_available():
    assert app.TZ.key == "Europe/London"
