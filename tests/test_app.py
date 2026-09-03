from datetime import datetime, timedelta, timezone

import app
import store

def client(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "notes.sqlite3")
    flask = app.create_app({"TESTING": True, "SECRET_KEY": "test"})
    return flask.test_client()

def csrf(c):
    c.get("/")
    with c.session_transaction() as session:
        return session["csrf_token"]

def test_capture_search_archive_restore_and_export(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch); token = csrf(c)
    response = c.post(
        "/new",
        data={
            "csrf_token": token,
            "title": "Book flight",
            "body": "Check Budapest",
            "tags": "Travel, AYCF",
            "colour": "violet",
        },
    )
    assert response.status_code == 302
    assert b"Book flight" in c.get("/?q=Budapest").data
    note = store.list_notes()[0]
    c.post(f"/notes/{note['id']}/archive", data={"csrf_token": token})
    assert not store.list_notes()
    assert len(store.list_notes("archive")) == 1
    assert c.get("/export.json").json["notes"][0]["tags"] == ["travel", "aycf"]

def test_due_reminder_can_be_snoozed(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch); token = csrf(c)
    due = (datetime.now() + timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
    c.post(
        "/new",
        data={
            "csrf_token": token,
            "title": "Call",
            "body": "",
            "tags": "",
            "colour": "slate",
            "due_at": due,
            "recurrence": "weekly",
        },
    )
    note = store.get_note(store.list_notes()[0]["id"])
    assert note["reminder"]["recurrence"] == "weekly"
    c.post(
        f"/reminders/{note['reminder']['id']}/snooze",
        data={"csrf_token": token, "minutes": "60"},
    )
    changed = store.get_note(note["id"])["reminder"]
    assert changed["due_at"] > note["reminder"]["due_at"]

def test_quick_recurring_reminder(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch); token = csrf(c)
    before = datetime.now(timezone.utc)
    response = c.post(
        "/quick-reminder",
        data={
            "csrf_token": token,
            "title": "Take a break",
            "preset": "1h",
            "recurrence": "daily",
        },
    )
    assert response.status_code == 302
    note = store.list_notes()[0]
    due = datetime.fromisoformat(note["reminder"]["due_at"])
    assert note["title"] == "Take a break"
    assert note["reminder"]["recurrence"] == "daily"
    assert timedelta(minutes=59) <= due - before <= timedelta(minutes=61)

def test_quick_checklist_items_can_be_ticked_searched_and_exported(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch); token = csrf(c)
    response = c.post(
        "/quick-checklist",
        data={
            "csrf_token": token,
            "title": "Trip packing",
            "items": "Passport\nCharger\n\nShoes",
        },
    )
    assert response.status_code == 302
    note = store.list_notes()[0]
    assert [item["text"] for item in note["checklist"]] == ["Passport", "Charger", "Shoes"]
    assert b"Trip packing" in c.get("/?q=Passport").data

    first = note["checklist"][0]
    response = c.post(
        f"/notes/{note['id']}/items/{first['id']}/toggle",
        data={"csrf_token": token},
    )
    assert response.status_code == 302
    changed = store.get_note(note["id"])
    assert changed["checklist_done"] == 1
    assert changed["checklist"][0]["completed"] == 1

    exported = c.get("/export.json").json
    assert exported["version"] == 2
    assert exported["checklist_items"][0]["text"] == "Passport"
    assert exported["checklist_items"][0]["completed"] == 1

def test_checklist_item_cannot_be_changed_through_another_note(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch); token = csrf(c)
    first_note = store.save_note(None, "First", "", "", "slate")
    second_note = store.save_note(None, "Second", "", "", "slate")
    store.add_checklist_items(first_note, "Private item")
    item = store.get_note(first_note)["checklist"][0]
    response = c.post(
        f"/notes/{second_note}/items/{item['id']}/toggle",
        data={"csrf_token": token},
    )
    assert response.status_code == 404
    assert store.get_note(first_note)["checklist"][0]["completed"] == 0

def test_mutations_require_csrf(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    assert c.post("/new", data={"title": "No"}).status_code == 400
    assert c.post("/quick-reminder", data={"title": "No"}).status_code == 400
    assert c.post("/quick-checklist", data={"title": "No"}).status_code == 400

def test_configured_timezone_is_available():
    assert app.TZ.key == "Europe/London"

def test_smart_views_separate_overdue_and_upcoming(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch)
    overdue = store.save_note(None, "Late task", "", "", "slate")
    future = store.save_note(None, "Future task", "", "", "slate")
    store.set_reminder(
        overdue,
        (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec="seconds"),
        "none",
    )
    store.set_reminder(
        future,
        (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(timespec="seconds"),
        "none",
    )
    overdue_page = c.get("/?view=notes&focus=overdue").get_data(as_text=True)
    upcoming_page = c.get("/?view=notes&focus=upcoming").get_data(as_text=True)
    assert "Late task" in overdue_page and "Future task" not in overdue_page
    assert "Future task" in upcoming_page and "Late task" not in upcoming_page

def test_important_reminder_is_pinned_and_completed_items_can_be_cleared(tmp_path, monkeypatch):
    c = client(tmp_path, monkeypatch); token = csrf(c)
    c.post(
        "/quick-reminder",
        data={
            "csrf_token": token,
            "title": "Important call",
            "preset": "1h",
            "recurrence": "none",
            "important": "1",
        },
    )
    reminder_note = store.list_notes()[0]
    assert reminder_note["pinned"] == 1

    checklist = store.save_note(None, "Tasks", "", "", "green")
    store.add_checklist_items(checklist, "Done\nKeep")
    first = store.get_note(checklist)["checklist"][0]
    store.toggle_checklist_item(checklist, first["id"])
    response = c.post(
        f"/notes/{checklist}/items/clear-completed",
        data={"csrf_token": token},
    )
    assert response.status_code == 302
    assert [item["text"] for item in store.get_note(checklist)["checklist"]] == ["Keep"]
