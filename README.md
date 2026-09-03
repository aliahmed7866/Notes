# Notes

A private, local-first notes and reminders app designed for a phone running Termux.

## First release

- quick capture with advanced reminder options disclosed only when needed
- tags, colours, pinning, archive, trash and full-text search
- one-off, daily, weekly and monthly reminders
- reminder snooze, completion and automatic recurring rollover
- Android notifications through Termux:API
- SQLite persistence outside the repository
- JSON export, CSRF protection and a localhost health endpoint
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
