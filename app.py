from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for

import store

COLOURS = {"slate", "violet", "blue", "green", "amber", "rose"}
TZ = ZoneInfo(os.environ.get("NOTES_TIMEZONE", "Europe/London"))

def csrf_ok() -> bool:
    return bool(
        request.form.get("csrf_token")
        and session.get("csrf_token")
        and hmac.compare_digest(request.form["csrf_token"], session["csrf_token"])
    )

def local_to_utc(value: str) -> str | None:
    if not value:
        return None
    try:
        local = datetime.fromisoformat(value).replace(tzinfo=TZ)
        return local.astimezone(timezone.utc).isoformat(timespec="seconds")
    except ValueError:
        return None

def utc_to_local(value: str | None) -> str:
    if not value:
        return ""
    return datetime.fromisoformat(value).astimezone(TZ).strftime("%Y-%m-%dT%H:%M")

def quick_due_utc(preset: str, custom: str = "", now: datetime | None = None) -> str | None:
    current = (now or datetime.now(TZ)).astimezone(TZ).replace(second=0, microsecond=0)
    if preset == "10m":
        due = current + timedelta(minutes=10)
    elif preset == "1h":
        due = current + timedelta(hours=1)
    elif preset == "evening":
        due = current.replace(hour=19, minute=0)
        if due <= current:
            due += timedelta(days=1)
    elif preset == "tomorrow":
        due = (current + timedelta(days=1)).replace(hour=9, minute=0)
    elif preset == "custom":
        return local_to_utc(custom)
    else:
        return None
    return due.astimezone(timezone.utc).isoformat(timespec="seconds")

def create_app(test_config=None):
    app = Flask(__name__)
    app.secret_key = os.environ.get("NOTES_SECRET_KEY") or secrets.token_urlsafe(32)
    if test_config:
        app.config.update(test_config)

    @app.before_request
    def token():
        session.setdefault("csrf_token", secrets.token_urlsafe(24))

    @app.context_processor
    def helpers():
        return {"csrf": session.get("csrf_token", ""), "local_due": utc_to_local}

    @app.get("/")
    def index():
        view = request.args.get("view", "notes")
        if view not in {"notes", "archive", "trash"}:
            view = "notes"
        focus = request.args.get("focus", "").strip()
        if focus not in {"", "today", "upcoming", "overdue"}:
            focus = ""
        query = request.args.get("q", "").strip()[:100]
        tag = request.args.get("tag", "").strip()[:30]
        notes = store.list_notes(view, query, tag, focus)
        now = store.now_iso()
        due = sum(1 for note in notes if note.get("reminder") and note["reminder"]["due_at"] <= now)
        return render_template(
            "index.html",
            notes=notes,
            view=view,
            q=query,
            tag=tag,
            tags=store.all_tags(),
            due=due,
            focus=focus,
            smart_counts=store.smart_counts(),
        )

    @app.post("/quick-reminder")
    def quick_reminder():
        if not csrf_ok():
            abort(400)
        title = request.form.get("title", "").strip()
        if not title:
            flash("Give the reminder a short title.")
            return redirect(url_for("index"))
        due = quick_due_utc(
            request.form.get("preset", "10m"),
            request.form.get("custom_due", ""),
        )
        if not due:
            flash("Choose a valid reminder time.")
            return redirect(url_for("index"))
        note_id = store.save_note(
            None,
            title,
            request.form.get("body", "").strip(),
            "reminder",
            "violet",
        )
        store.set_reminder(note_id, due, request.form.get("recurrence", "none"))
        if request.form.get("important") == "1":
            store.set_flag(note_id, "pinned", 1)
        flash("Reminder created.")
        return redirect(url_for("index"))

    @app.post("/quick-checklist")
    def quick_checklist():
        if not csrf_ok():
            abort(400)
        title = request.form.get("title", "").strip()
        items = request.form.get("items", "")
        if not title and not items.strip():
            flash("Add a checklist title or at least one item.")
            return redirect(url_for("index"))
        note_id = store.save_note(None, title or "Checklist", "", "todo", "green")
        store.add_checklist_items(note_id, items)
        flash("Checklist created.")
        return redirect(url_for("index"))

    @app.route("/new", methods=["GET", "POST"])
    @app.route("/notes/<int:note_id>/edit", methods=["GET", "POST"])
    def edit(note_id=None):
        note = store.get_note(note_id) if note_id else None
        if note_id and not note:
            abort(404)
        if request.method == "POST":
            if not csrf_ok():
                abort(400)
            title = request.form.get("title", "").strip()
            body = request.form.get("body", "").strip()
            new_items = request.form.get("new_items", "")
            if not title and not body and not new_items.strip():
                flash("Add a title, note text or checklist item.")
                return render_template("edit.html", note=note)
            colour = request.form.get("colour", "slate")
            if colour not in COLOURS:
                colour = "slate"
            saved = store.save_note(
                note_id,
                title,
                body,
                request.form.get("tags", ""),
                colour,
            )
            store.add_checklist_items(saved, new_items)
            due = local_to_utc(request.form.get("due_at", ""))
            if due:
                store.set_reminder(saved, due, request.form.get("recurrence", "none"))
            flash("Note saved.")
            return redirect(url_for("index"))
        return render_template("edit.html", note=note)

    @app.post("/notes/<int:note_id>/items")
    def add_checklist_item(note_id):
        if not csrf_ok():
            abort(400)
        if not store.get_note(note_id):
            abort(404)
        store.add_checklist_items(note_id, request.form.get("items", ""))
        return redirect(request.referrer or url_for("index"))

    @app.post("/notes/<int:note_id>/items/clear-completed")
    def clear_completed_items(note_id):
        if not csrf_ok():
            abort(400)
        if not store.get_note(note_id):
            abort(404)
        removed = store.clear_completed_items(note_id)
        flash(f"Cleared {removed} completed item{'s' if removed != 1 else ''}.")
        return redirect(request.referrer or url_for("index"))

    @app.post("/notes/<int:note_id>/items/<int:item_id>/<action>")
    def checklist_action(note_id, item_id, action):
        if not csrf_ok():
            abort(400)
        if action == "toggle":
            changed = store.toggle_checklist_item(note_id, item_id)
        elif action == "delete":
            changed = store.delete_checklist_item(note_id, item_id)
        else:
            abort(404)
        if not changed:
            abort(404)
        return redirect(request.referrer or url_for("index"))

    @app.post("/notes/<int:note_id>/<action>")
    def note_action(note_id, action):
        if not csrf_ok():
            abort(400)
        note = store.get_note(note_id)
        if not note:
            abort(404)
        if action == "pin":
            store.set_flag(note_id, "pinned", 0 if note["pinned"] else 1)
        elif action == "archive":
            store.set_flag(note_id, "archived", 0 if note["archived"] else 1)
        elif action == "trash":
            store.set_flag(note_id, "deleted_at", store.now_iso())
        elif action == "restore":
            store.set_flag(note_id, "deleted_at", None)
        else:
            abort(404)
        return redirect(request.referrer or url_for("index"))

    @app.post("/reminders/<int:reminder_id>/<action>")
    def reminder_action(reminder_id, action):
        if not csrf_ok():
            abort(400)
        if action == "snooze":
            minutes = int(request.form.get("minutes", "10"))
            minutes = minutes if minutes in {10, 60, 1440} else 10
            store.reminder_action(
                reminder_id,
                "snooze",
                (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(timespec="seconds"),
            )
        elif action in {"done", "cancel"}:
            store.reminder_action(reminder_id, action)
        else:
            abort(404)
        return redirect(request.referrer or url_for("index"))

    @app.get("/export.json")
    def export():
        return jsonify(store.export_data())

    @app.get("/service-worker.js")
    def service_worker():
        response = app.send_static_file("service-worker.js")
        response.headers["Content-Type"] = "application/javascript"
        response.headers["Cache-Control"] = "no-cache"
        response.headers["Service-Worker-Allowed"] = "/"
        return response

    @app.get("/health")
    def health():
        with store.connect() as db:
            db.execute("SELECT 1").fetchone()
        return {"ok": True}

    return app

app = create_app()
