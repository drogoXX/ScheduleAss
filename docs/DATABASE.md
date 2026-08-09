# Database location and backup

Status: **open decision, deferred.** Nothing here has been applied. The
application currently runs with the database in its default location. This
records the findings so the decision can be made later without re-deriving
them.

## Current state (measured 2026-08-09)

| Property | Value |
|---|---|
| Path | `<repo>/instance/schedule_analyzer.db` |
| Size | 6.4 MB (1 project, 1 schedule, 1756 activities) |
| Journal mode | **WAL** |
| `synchronous` | FULL (2) |
| `integrity_check` | **ok** |
| Conflict copies / stray `-wal`, `-shm` | none |
| Location | inside a **OneDrive-synced** folder |

Nothing is damaged today. This is a risk to remove before the dataset grows,
not an incident to clean up.

## Why the current location is a problem

SQLite in WAL mode keeps a `-wal` write-ahead log and a `-shm` shared-memory
file alongside the database, and relies on file locking to keep them
consistent. Cloud sync clients honour neither: OneDrive uploads each file
independently, so it can capture the `.db` at one instant and the `-wal` at
another.

Three consequences, in order of severity:

1. **The cloud copy can be inconsistent even when the local file is fine.**
   That is the copy you would restore from, so the damage is discovered only
   when it is needed.
2. **Conflict copies.** If this OneDrive account ever syncs to a second machine
   and the application runs there, OneDrive produces
   `schedule_analyzer-DESKTOP-XYZ.db` and two databases diverge with no merge
   path.
3. **Churn.** The full 6.4 MB is re-uploaded after every write.

The same cloud-sync activity is what caused the navigation failures fixed in
`.streamlit/config.toml` (`fileWatcherType = "none"`) — see that file's
comments. Disabling the watcher fixed the symptom; the database sitting in a
synced tree is the remaining part of the same underlying issue.

## Options

### A. Move the runtime data directory off OneDrive (recommended)

`src/config.py` resolves `APP_DATA_DIR` (default `<repo>/instance`) and derives
both the database and the log directory from it, so **one variable moves
everything**:

```ini
# .env  (already gitignored; python-dotenv is a runtime dependency)
APP_DATA_DIR=C:\Users\<user>\AppData\Local\ScheduleQualityAnalyzer
```

Migration:

1. Stop the application.
2. Create the target directory.
3. Copy `instance/schedule_analyzer.db` into it (copy, do not move — the
   original stays as a fallback until the new location is proven).
4. Set `APP_DATA_DIR` in `.env`.
5. Start the application and confirm the projects and schedules are present.

`APP_DB_PATH` and `APP_LOG_DIR` exist if the database and logs need to live in
different places; `APP_DATA_DIR` alone is sufficient for the normal case.

### B. Keep it on OneDrive, switch WAL off

Setting `journal_mode = DELETE` removes the `-wal`/`-shm` sidecars and shrinks
the corruption surface. It does **not** make cloud sync safe — SQLite's locking
is still not honoured. A mitigation, not a fix.

### C. Move the whole working copy off OneDrive

Relocating the repository (e.g. `C:\dev\Schedule`) and relying on git for
off-machine copies resolves this at the source, and would also remove the need
for `fileWatcherType = "none"`. It changes the working setup and any desktop
shortcut.

### D. Move to a client/server database

Only worth considering if this is deployed for concurrent users rather than run
locally. The application has roles and an audit log, so multi-user is plausible;
SQLite is a poor fit for genuinely concurrent writers over a network.

## Backups

Option A gives up OneDrive's automatic version history, so it must be replaced
rather than simply dropped.

The safe pattern is **sync backups, not the live database**: SQLite's
`VACUUM INTO` writes a consistent, checkpointed snapshot that is safe to copy
into a synced folder, unlike an open database file.

Sketch of `tools/backup_db.py` (not yet written):

```python
# Consistent snapshot, safe to place in OneDrive
conn.execute("VACUUM INTO ?", [str(target)])
```

with a timestamped filename, a retention limit, and either manual invocation,
Windows Task Scheduler, or a call at application start.

Never copy a live `.db` with `shutil.copy` while the application is running —
that reintroduces exactly the inconsistency described above.

## Git hygiene (already correct — no action)

Verified against the index on 2026-08-09: nothing sensitive is tracked.
`.gitignore` covers `instance/`, `*.db`, `*.db-wal`, `*.db-shm`, `*.log`,
`.env`, and the client material in `Schedule extract/`, `input/` and `*.xer`.

Note that `*.docx` is ignored, so `Schedule_Quality_Analyzer_User_Guide.docx` is
not in the repository. It is regenerable with
`python tools/build_user_guide_docx.py`.
