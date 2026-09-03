from __future__ import annotations

import calendar
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DB_PATH = Path(os.environ.get("NOTES_DB_PATH", Path.home() / ".local/share/notes/notes.sqlite3")).expanduser()

SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
 id INTEGER PRIMARY KEY, title TEXT NOT NULL DEFAULT '', body TEXT NOT NULL DEFAULT '',
 tags TEXT NOT NULL DEFAULT '[]', colour TEXT NOT NULL DEFAULT 'slate',
 pinned INTEGER NOT NULL DEFAULT 0, archived INTEGER NOT NULL DEFAULT 0,
 deleted_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
 id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
 due_at TEXT NOT NULL, recurrence TEXT NOT NULL DEFAULT 'none',
 status TEXT NOT NULL DEFAULT 'pending', notified_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS checklist_items (
 id INTEGER PRIMARY KEY, note_id INTEGER NOT NULL REFERENCES notes(id) ON DELETE CASCADE,
 text TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
 position INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_updated ON notes(pinned DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(status, due_at);
CREATE INDEX IF NOT EXISTS idx_checklist_note ON checklist_items(note_id, position, id);
"""

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def connect(path: Path | None = None) -> sqlite3.Connection:
    target = path or DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(target)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    return db

def tags_from(raw: str) -> list[str]:
    seen = set()
    out = []
    for item in raw.replace(",", " ").split():
        tag = item.strip().lstrip("#").lower()[:30]
        if tag and tag not in seen:
            seen.add(tag); out.append(tag)
    return out[:12]

def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    if "tags" in item:
        try: item["tags"] = json.loads(item["tags"])
        except Exception: item["tags"] = []
    return item

def _decorate_note(db: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    item = row_dict(row)
    reminder = db.execute(
        "SELECT * FROM reminders WHERE note_id=? AND status='pending' ORDER BY due_at LIMIT 1",
        (item["id"],),
    ).fetchone()
    item["reminder"] = dict(reminder) if reminder else None
    item["checklist"] = [
        dict(check)
        for check in db.execute(
            "SELECT * FROM checklist_items WHERE note_id=? ORDER BY position,id",
            (item["id"],),
        )
    ]
    item["checklist_done"] = sum(check["completed"] for check in item["checklist"])
    return item

def list_notes(view="notes", query="", tag="") -> list[dict[str, Any]]:
    clauses, args = [], []
    if view == "trash": clauses.append("deleted_at IS NOT NULL")
    else:
        clauses.append("deleted_at IS NULL")
        clauses.append("archived=?"); args.append(1 if view == "archive" else 0)
    if query:
        clauses.append("""(
            title LIKE ? OR body LIKE ? OR tags LIKE ? OR EXISTS (
                SELECT 1 FROM checklist_items c
                WHERE c.note_id=notes.id AND c.text LIKE ?
            )
        )""")
        like = f"%{query}%"; args += [like, like, like, like]
    if tag:
        clauses.append("tags LIKE ?"); args.append(f'%"{tag.lower()}"%')
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM notes WHERE " + " AND ".join(clauses) +
            " ORDER BY pinned DESC, updated_at DESC",
            args,
        ).fetchall()
        return [_decorate_note(db, row) for row in rows]

def get_note(note_id: int) -> dict[str, Any] | None:
    with connect() as db:
        row = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        return _decorate_note(db, row) if row else None

def save_note(note_id: int | None, title: str, body: str, tags: str, colour: str) -> int:
    now = now_iso(); payload = json.dumps(tags_from(tags))
    with connect() as db:
        if note_id:
            db.execute(
                "UPDATE notes SET title=?,body=?,tags=?,colour=?,updated_at=? WHERE id=? AND deleted_at IS NULL",
                (title[:200], body[:50000], payload, colour, now, note_id),
            )
            return note_id
        cur = db.execute(
            "INSERT INTO notes(title,body,tags,colour,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (title[:200], body[:50000], payload, colour, now, now),
        )
        return int(cur.lastrowid)

def add_checklist_items(note_id: int, raw_items: str) -> int:
    items = [line.strip()[:500] for line in raw_items.splitlines() if line.strip()]
    if not items:
        return 0
    with connect() as db:
        start = db.execute(
            "SELECT COALESCE(MAX(position),-1)+1 FROM checklist_items WHERE note_id=?",
            (note_id,),
        ).fetchone()[0]
        db.executemany(
            "INSERT INTO checklist_items(note_id,text,position,created_at) VALUES(?,?,?,?)",
            [(note_id, text, start + index, now_iso()) for index, text in enumerate(items[:100])],
        )
        db.execute("UPDATE notes SET updated_at=? WHERE id=?", (now_iso(), note_id))
    return min(len(items), 100)

def toggle_checklist_item(note_id: int, item_id: int) -> bool:
    with connect() as db:
        changed = db.execute(
            """UPDATE checklist_items
               SET completed=CASE completed WHEN 1 THEN 0 ELSE 1 END
               WHERE id=? AND note_id=?""",
            (item_id, note_id),
        ).rowcount
        if changed:
            db.execute("UPDATE notes SET updated_at=? WHERE id=?", (now_iso(), note_id))
    return bool(changed)

def delete_checklist_item(note_id: int, item_id: int) -> bool:
    with connect() as db:
        changed = db.execute(
            "DELETE FROM checklist_items WHERE id=? AND note_id=?",
            (item_id, note_id),
        ).rowcount
        if changed:
            db.execute("UPDATE notes SET updated_at=? WHERE id=?", (now_iso(), note_id))
    return bool(changed)

def set_flag(note_id: int, field: str, value: Any) -> None:
    allowed = {"pinned", "archived", "deleted_at"}
    if field not in allowed: raise ValueError("invalid field")
    with connect() as db:
        db.execute(f"UPDATE notes SET {field}=?,updated_at=? WHERE id=?", (value, now_iso(), note_id))

def set_reminder(note_id: int, due_at: str, recurrence: str) -> None:
    if recurrence not in {"none", "daily", "weekly", "monthly"}: recurrence = "none"
    with connect() as db:
        db.execute("UPDATE reminders SET status='replaced' WHERE note_id=? AND status='pending'", (note_id,))
        db.execute(
            "INSERT INTO reminders(note_id,due_at,recurrence,status,created_at) VALUES(?,?,?,'pending',?)",
            (note_id, due_at, recurrence, now_iso()),
        )

def reminder_action(reminder_id: int, action: str, due_at: str | None = None) -> None:
    with connect() as db:
        if action == "snooze" and due_at:
            db.execute(
                "UPDATE reminders SET due_at=?,notified_at=NULL WHERE id=? AND status='pending'",
                (due_at, reminder_id),
            )
        elif action == "done":
            row = db.execute(
                "SELECT note_id,due_at,recurrence FROM reminders WHERE id=? AND status='pending'",
                (reminder_id,),
            ).fetchone()
            db.execute("UPDATE reminders SET status='done' WHERE id=?", (reminder_id,))
            if row and row["recurrence"] != "none":
                zone = ZoneInfo(os.environ.get("NOTES_TIMEZONE", "Europe/London"))
                due = datetime.fromisoformat(row["due_at"]).astimezone(zone)
                now = datetime.now(timezone.utc)
                while due.astimezone(timezone.utc) <= now:
                    if row["recurrence"] == "daily": due += timedelta(days=1)
                    elif row["recurrence"] == "weekly": due += timedelta(days=7)
                    else:
                        year = due.year + (1 if due.month == 12 else 0)
                        month = 1 if due.month == 12 else due.month + 1
                        due = due.replace(
                            year=year,
                            month=month,
                            day=min(due.day, calendar.monthrange(year, month)[1]),
                        )
                next_utc = due.astimezone(timezone.utc).isoformat(timespec="seconds")
                db.execute(
                    "INSERT INTO reminders(note_id,due_at,recurrence,status,created_at) VALUES(?,?,?,'pending',?)",
                    (row["note_id"], next_utc, row["recurrence"], now_iso()),
                )
        elif action == "cancel":
            db.execute("UPDATE reminders SET status='cancelled' WHERE id=?", (reminder_id,))

def due_reminders(now: str) -> list[dict[str, Any]]:
    with connect() as db:
        rows = db.execute(
            """SELECT r.*,n.title,n.body FROM reminders r JOIN notes n ON n.id=r.note_id
               WHERE r.status='pending' AND r.due_at<=? AND r.notified_at IS NULL
               AND n.deleted_at IS NULL""",
            (now,),
        ).fetchall()
    return [dict(r) for r in rows]

def mark_notified(reminder_id: int) -> None:
    with connect() as db:
        db.execute("UPDATE reminders SET notified_at=? WHERE id=?", (now_iso(), reminder_id))

def all_tags() -> list[str]:
    out = set()
    with connect() as db:
        rows = db.execute("SELECT tags FROM notes WHERE deleted_at IS NULL").fetchall()
    for row in rows:
        try: out.update(json.loads(row["tags"]))
        except Exception: pass
    return sorted(out)

def export_data() -> dict[str, Any]:
    with connect() as db:
        notes = [row_dict(row) for row in db.execute("SELECT * FROM notes ORDER BY id")]
        reminders = [dict(row) for row in db.execute("SELECT * FROM reminders ORDER BY id")]
        checklist_items = [dict(row) for row in db.execute("SELECT * FROM checklist_items ORDER BY note_id,position,id")]
    return {
        "version": 2,
        "exported_at": now_iso(),
        "notes": notes,
        "reminders": reminders,
        "checklist_items": checklist_items,
    }
