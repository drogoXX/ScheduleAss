# Deployment & Operations Guide

Operational reference for running the Schedule Quality Analyzer in production.

---

## 1. Requirements

- Python 3.11+ (verified on 3.13)
- Writable persistent storage for the database and logs
- A reverse proxy terminating TLS (the app must not be exposed directly)

## 2. Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

For development and running the test suite:

```bash
pip install -r requirements-dev.txt
```

## 3. Configure

Copy `.env.example` to `.env` and set values for your environment. Every setting
is read from the environment; nothing deployment-specific is hard-coded.

```bash
cp .env.example .env
```

The settings that matter most:

| Variable | Purpose |
| --- | --- |
| `APP_ENV` | `production` hides stack traces and debug output. |
| `APP_DATA_DIR` | Where the SQLite database and logs are written. **Must be on persistent storage.** |
| `APP_ADMIN_PASSWORD` | Password for the bootstrap admin, applied only on first start. |
| `APP_DATE_ORDER` | `auto`, `day`, or `month`. See "Date formats" below. |
| `APP_MAX_UPLOAD_MB` | Upload ceiling enforced in application code. |
| `APP_LOG_LEVEL` | `INFO` in normal operation; `DEBUG` when diagnosing. |

`APP_MAX_UPLOAD_MB` and `server.maxUploadSize` in `.streamlit/config.toml` guard
different layers (application vs transport). **Keep them in step** — otherwise a
file is either rejected by Streamlit before the app can explain why, or accepted
by Streamlit and then refused by the app.

## 4. First start

```bash
streamlit run app.py
```

On the very first start, with an empty user table, the application creates one
administrator:

- If `APP_ADMIN_PASSWORD` is set, that password is used.
- If it is **not** set, a strong random password is generated and written to the
  application log as a `WARNING`. Retrieve it from `<APP_DATA_DIR>/logs/app.log`,
  sign in, and change it immediately.

The bootstrap runs only while no users exist. It will never silently reset or
overwrite an existing administrator.

> The previous release shipped with `admin`/`admin123` and `viewer`/`viewer123`
> hard-coded **and printed them on the login page**. Those accounts no longer
> exist. Any deployment upgraded from that version should be treated as
> compromised: rotate credentials and review the audit log.

## 5. Run behind a reverse proxy

Streamlit should not face the internet directly. Terminate TLS at nginx/Caddy
and proxy to the app, preserving websocket upgrades:

```nginx
location / {
    proxy_pass         http://127.0.0.1:8501;
    proxy_http_version 1.1;
    proxy_set_header   Upgrade $http_upgrade;
    proxy_set_header   Connection "upgrade";
    proxy_set_header   Host $host;
    proxy_set_header   X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header   X-Forwarded-Proto $scheme;
}
```

Bind the app to localhost so it is only reachable through the proxy:

```bash
streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## 6. Data, backups and logs

Everything durable lives under `APP_DATA_DIR`:

```
instance/
├── schedule_analyzer.db        # SQLite: users, projects, schedules, analyses, audit log
├── schedule_analyzer.db-wal    # write-ahead log
├── schedule_analyzer.db-shm
└── logs/
    └── app.log                 # rotating, 5 MB x 5
```

Back up with SQLite's online backup, which is safe while the app is running.
Copying the `.db` file directly can capture a torn write:

```bash
sqlite3 instance/schedule_analyzer.db ".backup 'backup-$(date +%F).db'"
```

Restore by stopping the app, replacing the database file (remove stale `-wal`
and `-shm` alongside it), and starting again.

### Scaling note

SQLite comfortably handles the concurrency of a typical departmental
deployment: WAL mode allows concurrent readers with a single writer, and writes
here are short and infrequent (upload, analyse, delete). If this grows to many
simultaneous uploaders, migrate to PostgreSQL — `DatabaseManager` is the only
module that touches storage, so the change is contained to that one file.

## 7. Date formats

P6 exports dates in the exporting machine's locale, with no marker saying which
one. `29/08/2025` is unambiguous, but `03/04/2025` could be 3 April or 4 March.

The parser inspects **every** date in the file and picks the only order
consistent with the data. It reports what it chose in the upload warnings, and
says so explicitly when a file is genuinely ambiguous. ISO dates
(`2025-04-03`) are always detected and never reinterpreted.

If a schedule is entirely ambiguous, set `APP_DATE_ORDER=day` or `month` to
match the source system. **Best practice: export from P6 using `YYYY-MM-DD`**,
which removes the guesswork.

## 8. Health checks

Streamlit serves a health endpoint suitable for load balancers:

```bash
curl -f http://127.0.0.1:8501/healthz
```

Note this reports that the *server* is up. It does not execute the application
script, so it will not detect a failure that only appears once a user session
starts.

## 9. Tests

```bash
python -m pytest                      # full suite
python -m pytest --cov=src            # with coverage
python -m pytest tests/test_parser.py # one module
```

The suite is self-contained: every test runs against a temporary database and
never touches production data.

The scripts in `archive/dev_scripts/` are historical debugging aids, not tests.
They are excluded from collection and are not maintained.

## 10. Security posture

Implemented:

- Passwords stored as salted PBKDF2-HMAC-SHA256 (600,000 iterations), verified
  in constant time, with transparent rehashing when the cost factor is raised.
- Temporary account lockout after repeated failed logins.
- Role-based access control enforced on every page.
- Idle session expiry (60 minutes) and session data cleared on login and logout.
- All SQL parameterised.
- CSV-derived content HTML-escaped before rendering.
- Stack traces logged server-side only; users see a generic message plus an
  error reference for support.
- Audit log of logins, uploads, exports and deletions.

Deployment responsibilities:

- **Serve over HTTPS.** Session cookies and credentials are otherwise in clear.
- Restrict filesystem permissions on `APP_DATA_DIR`; the SQLite file holds all
  schedule data.
- Keep `.env` out of version control (already in `.gitignore`).
- Rotate the bootstrap admin password after first sign-in.

Not implemented — evaluate against your requirements:

- No multi-factor authentication.
- No password reset flow; an admin resets passwords via Settings.
- The SQLite file is not encrypted at rest; use an encrypted volume if the
  schedule data is sensitive.
