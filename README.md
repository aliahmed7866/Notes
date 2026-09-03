# Notes

A private, local-first notes, checklists and reminders app designed for a phone running Termux.

## Features

- dashboard quick reminder creation with 10-minute, 1-hour, evening, tomorrow and custom-time choices
- one-off, daily, weekly and monthly recurring reminders
- smart Today, Upcoming and Overdue views with due-date ordering and live counts
- important reminders that stay pinned at the top
- quick checklists with one item per line
- checklist progress, one-tap tick/untick, item addition, deletion and completed-item cleanup
- search across titles, note text, checklist items and tags
- tags, colours, pinning, archive and trash
- reminder snooze, completion and automatic recurring rollover
- Android notifications through Termux:API
- SQLite persistence outside the repository
- JSON export (including checklist state), CSRF protection and a localhost health endpoint
- runit services for the web app, reminder worker and automatic deployment

## Termux

```bash
git clone https://github.com/aliahmed7866/Notes.git ~/Notes
cd ~/Notes
bash termux/install-service.sh
bash termux/install-auto-deploy.sh
```

Open http://127.0.0.1:8083. Data defaults to `~/.local/share/notes/notes.sqlite3`.

Install Termux:API from the same source/signature as Termux and allow notifications for Android reminders.

## Updating

When this feature is merged, the normal auto-deploy service will pull it. For a manual update:

```bash
cd ~/Notes
git pull --ff-only origin main
bash termux/install-service.sh
```

The checklist table is created automatically on first start; existing notes and reminders are preserved.
