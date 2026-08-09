"""
Database Manager (SQLite)

Durable storage for users, projects, schedules, analysis results and the audit
log. Replaces the previous session_state store, which lost every record on page
refresh and never shared data between users.

The public method surface is unchanged from the session_state implementation so
existing pages continue to work.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional

from src.auth.security import hash_password, needs_rehash, verify_password
from src.config import ensure_directories, settings
from src.database import serialization
from src.logging_config import get_logger

logger = get_logger("database")

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT NOT NULL,
    username        TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'viewer')),
    is_active       INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created         TEXT NOT NULL,
    updated         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id           TEXT PRIMARY KEY,
    project_name TEXT NOT NULL,
    project_code TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description  TEXT,
    created_by   TEXT,
    created      TEXT NOT NULL,
    updated      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS schedules (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    schedule_data   TEXT NOT NULL,
    file_name       TEXT NOT NULL,
    upload_date     TEXT NOT NULL,
    uploaded_by     TEXT,
    analysis_status TEXT NOT NULL DEFAULT 'pending'
);
CREATE INDEX IF NOT EXISTS idx_schedules_project ON schedules(project_id);

CREATE TABLE IF NOT EXISTS analysis_results (
    id              TEXT PRIMARY KEY,
    schedule_id     TEXT NOT NULL UNIQUE REFERENCES schedules(id) ON DELETE CASCADE,
    metrics         TEXT NOT NULL,
    issues          TEXT NOT NULL,
    recommendations TEXT NOT NULL,
    extra           TEXT,
    health_score    REAL NOT NULL,
    analysis_date   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT,
    action_type TEXT NOT NULL,
    resource_id TEXT,
    details     TEXT,
    timestamp   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);

CREATE TABLE IF NOT EXISTS schema_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DatabaseManager:
    """SQLite-backed persistence layer."""

    def __init__(self, db_path: Optional[str] = None):
        ensure_directories()
        self.db_path = str(db_path or settings.db_path)
        # Serialises writes from Streamlit's per-session threads.
        self._lock = threading.RLock()
        self._initialize()

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path, timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA busy_timeout = 30000")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES ('version', ?)",
                (str(SCHEMA_VERSION),),
            )
        self._bootstrap_admin()

    def _bootstrap_admin(self) -> None:
        """
        Seed the initial admin account when the user table is empty.

        The password comes from APP_ADMIN_PASSWORD. If it is unset we generate a
        random one and log it once, so a deployment never silently ships with a
        guessable default.
        """
        with self._lock, self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            if count:
                return

        password = settings.BOOTSTRAP_ADMIN_PASSWORD
        generated = False
        if not password:
            from src.auth.security import generate_password

            password = generate_password()
            generated = True

        self.create_user(
            email=settings.BOOTSTRAP_ADMIN_EMAIL,
            username=settings.BOOTSTRAP_ADMIN_USERNAME,
            password=password,
            role="admin",
        )

        if generated:
            logger.warning(
                "No APP_ADMIN_PASSWORD set. Created bootstrap admin '%s' with a "
                "generated password: %s  -- change it and set APP_ADMIN_PASSWORD.",
                settings.BOOTSTRAP_ADMIN_USERNAME,
                password,
            )
        else:
            logger.info("Created bootstrap admin '%s'", settings.BOOTSTRAP_ADMIN_USERNAME)

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------
    @staticmethod
    def _user_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Public user representation - never includes the password hash."""
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
            "role": row["role"],
            "is_active": bool(row["is_active"]),
            "created": row["created"],
            "updated": row["updated"],
        }

    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """
        Verify credentials.

        Returns the user dict on success, None otherwise. Applies temporary
        lockout after repeated failures and always runs a hash comparison so
        that timing does not reveal whether a username exists.
        """
        if not username or not password:
            return None

        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()

            if row is None:
                # Dummy verification keeps the timing profile uniform.
                verify_password(password, hash_password("not-a-real-password"))
                logger.info("Failed login for unknown user %r", username)
                return None

            if not row["is_active"]:
                logger.warning("Login attempt for disabled account %r", username)
                return None

            locked_until = row["locked_until"]
            if locked_until:
                try:
                    if datetime.fromisoformat(locked_until) > datetime.now(timezone.utc):
                        logger.warning("Login attempt for locked account %r", username)
                        return None
                except ValueError:
                    pass

            if not verify_password(password, row["password_hash"]):
                attempts = row["failed_attempts"] + 1
                lock_value = None
                if attempts >= settings.MAX_LOGIN_ATTEMPTS:
                    lock_value = (
                        datetime.now(timezone.utc)
                        + timedelta(seconds=settings.LOCKOUT_SECONDS)
                    ).isoformat()
                    logger.warning(
                        "Account %r locked after %d failed attempts", username, attempts
                    )
                conn.execute(
                    "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
                    (attempts, lock_value, row["id"]),
                )
                logger.info("Failed login for user %r", username)
                return None

            # Success - clear counters and upgrade the hash if the cost changed.
            password_hash = row["password_hash"]
            if needs_rehash(password_hash):
                password_hash = hash_password(password)

            conn.execute(
                "UPDATE users SET failed_attempts = 0, locked_until = NULL, "
                "password_hash = ? WHERE id = ?",
                (password_hash, row["id"]),
            )
            logger.info("Successful login for user %r", username)
            return self._user_to_dict(row)

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        if not user_id:
            return None
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._user_to_dict(row) if row else None

    def get_user_by_username(self, username: str) -> Optional[Dict]:
        if not username:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ? COLLATE NOCASE", (username,)
            ).fetchone()
            return self._user_to_dict(row) if row else None

    def get_all_users(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY created").fetchall()
            return [self._user_to_dict(r) for r in rows]

    def create_user(self, email: str, username: str, password: str,
                    role: str = "viewer") -> Dict:
        """Create a user with a hashed password. Raises ValueError on conflict."""
        if role not in ("admin", "viewer"):
            raise ValueError(f"Invalid role: {role!r}")
        if not username or not username.strip():
            raise ValueError("Username is required")

        username = username.strip()
        password_hash = hash_password(password)
        now = _now()

        with self._lock, self._connect() as conn:
            user_id = self._next_id(conn, "users", "user")
            try:
                conn.execute(
                    "INSERT INTO users (id, email, username, password_hash, role, "
                    "is_active, failed_attempts, created, updated) "
                    "VALUES (?, ?, ?, ?, ?, 1, 0, ?, ?)",
                    (user_id, email, username, password_hash, role, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"Username '{username}' already exists") from exc

            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._user_to_dict(row)

    def set_password(self, user_id: str, new_password: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE users SET password_hash = ?, updated = ?, failed_attempts = 0, "
                "locked_until = NULL WHERE id = ?",
                (hash_password(new_password), _now(), user_id),
            )
            return cursor.rowcount > 0

    def set_user_active(self, user_id: str, is_active: bool) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE users SET is_active = ?, updated = ? WHERE id = ?",
                (1 if is_active else 0, _now(), user_id),
            )
            return cursor.rowcount > 0

    @staticmethod
    def _next_id(conn: sqlite3.Connection, table: str, prefix: str) -> str:
        """
        Build the next human-readable id for a table.

        Takes the caller's connection so id allocation happens inside the same
        transaction as the insert; opening a second connection here would not
        see the enclosing transaction's uncommitted rows.
        """
        base = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"] + 1
        # Rows may have been deleted, so step past any id already in use.
        while conn.execute(
            f"SELECT 1 FROM {table} WHERE id = ?", (f"{prefix}_{base:03d}",)
        ).fetchone():
            base += 1
        return f"{prefix}_{base:03d}"

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------
    def create_project(self, project_name: str, project_code: str, description: str,
                       created_by: str) -> Dict:
        if not project_name or not project_name.strip():
            raise ValueError("Project name is required")
        if not project_code or not project_code.strip():
            raise ValueError("Project code is required")

        now = _now()

        with self._lock, self._connect() as conn:
            project_id = self._next_id(conn, "projects", "proj")
            try:
                conn.execute(
                    "INSERT INTO projects (id, project_name, project_code, description, "
                    "created_by, created, updated) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (project_id, project_name.strip(), project_code.strip(),
                     description, created_by, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(
                    f"Project code '{project_code}' already exists"
                ) from exc
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            project = dict(row)

        self._log_action(created_by, "create_project", project_id,
                         {"project_name": project_name})
        logger.info("Project %s created by %s", project_id, created_by)
        return project

    def get_all_projects(self) -> List[Dict]:
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                "SELECT * FROM projects ORDER BY created"
            ).fetchall()]

    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        if not project_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_project_by_code(self, project_code: str) -> Optional[Dict]:
        if not project_code:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM projects WHERE project_code = ? COLLATE NOCASE",
                (project_code.strip(),),
            ).fetchone()
            return dict(row) if row else None

    def delete_project(self, project_id: str, user_id: str) -> bool:
        """Delete a project and, by cascade, its schedules and analyses."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            deleted = cursor.rowcount > 0
        if deleted:
            self._log_action(user_id, "delete_project", project_id, {})
            logger.info("Project %s deleted by %s", project_id, user_id)
        return deleted

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------
    @staticmethod
    def _schedule_to_dict(row: sqlite3.Row, include_data: bool = True) -> Dict[str, Any]:
        schedule = {
            "id": row["id"],
            "project_id": row["project_id"],
            "version_number": row["version_number"],
            "file_name": row["file_name"],
            "upload_date": row["upload_date"],
            "uploaded_by": row["uploaded_by"],
            "analysis_status": row["analysis_status"],
        }
        if include_data:
            schedule["schedule_data"] = serialization.loads_schedule_data(
                row["schedule_data"]
            )
        return schedule

    def create_schedule(self, project_id: str, schedule_data: Dict, file_name: str,
                        uploaded_by: str) -> Dict:
        now = _now()
        payload = serialization.dumps_schedule_data(schedule_data)

        with self._lock, self._connect() as conn:
            if not conn.execute(
                "SELECT 1 FROM projects WHERE id = ?", (project_id,)
            ).fetchone():
                raise ValueError(f"Unknown project: {project_id}")

            version = conn.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS v FROM schedules "
                "WHERE project_id = ?",
                (project_id,),
            ).fetchone()["v"]

            schedule_id = self._next_id(conn, "schedules", "sched")
            conn.execute(
                "INSERT INTO schedules (id, project_id, version_number, schedule_data, "
                "file_name, upload_date, uploaded_by, analysis_status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
                (schedule_id, project_id, version, payload, file_name, now, uploaded_by),
            )
            row = conn.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
            schedule = self._schedule_to_dict(row)

        self._log_action(uploaded_by, "upload_schedule", schedule_id,
                         {"file_name": file_name, "project_id": project_id})
        logger.info(
            "Schedule %s (v%s, %s activities) uploaded to %s by %s",
            schedule_id, version, schedule_data.get("total_activities", "?"),
            project_id, uploaded_by,
        )
        return schedule

    def get_schedule_by_id(self, schedule_id: str) -> Optional[Dict]:
        if not schedule_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
            return self._schedule_to_dict(row) if row else None

    def get_schedules_by_project(self, project_id: str) -> List[Dict]:
        """Schedule metadata for a project (payloads omitted for efficiency)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schedules WHERE project_id = ? ORDER BY version_number",
                (project_id,),
            ).fetchall()
            return [self._schedule_to_dict(r, include_data=False) for r in rows]

    def get_all_schedules(self, include_data: bool = False) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM schedules ORDER BY upload_date"
            ).fetchall()
            return [self._schedule_to_dict(r, include_data=include_data) for r in rows]

    def count_schedules(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS n FROM schedules").fetchone()["n"]

    def update_schedule_status(self, schedule_id: str, status: str) -> bool:
        with self._lock, self._connect() as conn:
            cursor = conn.execute(
                "UPDATE schedules SET analysis_status = ? WHERE id = ?",
                (status, schedule_id),
            )
            return cursor.rowcount > 0

    def delete_schedule(self, schedule_id: str, user_id: str) -> bool:
        with self._lock, self._connect() as conn:
            # analysis_results cascades via the foreign key.
            cursor = conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
            deleted = cursor.rowcount > 0
        if deleted:
            self._log_action(user_id, "delete_schedule", schedule_id, {})
            logger.info("Schedule %s deleted by %s", schedule_id, user_id)
        return deleted

    # ------------------------------------------------------------------
    # Analysis results
    # ------------------------------------------------------------------
    @staticmethod
    def _analysis_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        analysis = {
            "id": row["id"],
            "schedule_id": row["schedule_id"],
            "metrics": serialization.loads(row["metrics"]),
            "issues": serialization.loads(row["issues"]),
            "recommendations": serialization.loads(row["recommendations"]),
            "health_score": row["health_score"],
            "analysis_date": row["analysis_date"],
        }
        if row["extra"]:
            analysis.update(serialization.loads(row["extra"]))
        return analysis

    def save_analysis_result(self, schedule_id: str, metrics: Dict, issues: List[Dict],
                             recommendations: List[Dict], health_score: float,
                             extra: Optional[Dict] = None) -> Dict:
        """
        Persist analysis output, replacing any previous result for the schedule.

        ``extra`` carries derived payloads (performance metrics, the DCMA
        14-point summary) that were previously attached to the returned dict in
        memory and therefore lost on refresh.
        """
        now = _now()

        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT id FROM analysis_results WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
            analysis_id = (
                existing["id"] if existing
                else self._next_id(conn, "analysis_results", "analysis")
            )

            conn.execute(
                "INSERT INTO analysis_results (id, schedule_id, metrics, issues, "
                "recommendations, extra, health_score, analysis_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(schedule_id) DO UPDATE SET "
                "metrics = excluded.metrics, issues = excluded.issues, "
                "recommendations = excluded.recommendations, extra = excluded.extra, "
                "health_score = excluded.health_score, "
                "analysis_date = excluded.analysis_date",
                (analysis_id, schedule_id, serialization.dumps(metrics),
                 serialization.dumps(issues), serialization.dumps(recommendations),
                 serialization.dumps(extra) if extra else None,
                 float(health_score), now),
            )
            conn.execute(
                "UPDATE schedules SET analysis_status = 'complete' WHERE id = ?",
                (schedule_id,),
            )
            row = conn.execute(
                "SELECT * FROM analysis_results WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
            return self._analysis_to_dict(row)

    def get_analysis_by_schedule(self, schedule_id: str) -> Optional[Dict]:
        if not schedule_id:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM analysis_results WHERE schedule_id = ?", (schedule_id,)
            ).fetchone()
            return self._analysis_to_dict(row) if row else None

    def get_all_analyses(self) -> List[Dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM analysis_results ORDER BY analysis_date"
            ).fetchall()
            return [self._analysis_to_dict(r) for r in rows]

    def count_analyses(self) -> int:
        with self._connect() as conn:
            return conn.execute(
                "SELECT COUNT(*) AS n FROM analysis_results"
            ).fetchone()["n"]

    # ------------------------------------------------------------------
    # Audit log
    # ------------------------------------------------------------------
    def _log_action(self, user_id: str, action_type: str, resource_id: str,
                    details: Dict) -> None:
        try:
            with self._lock, self._connect() as conn:
                conn.execute(
                    "INSERT INTO audit_log (user_id, action_type, resource_id, "
                    "details, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (user_id, action_type, resource_id,
                     serialization.dumps(details or {}), _now()),
                )
        except Exception:
            # Auditing must never break the user-facing operation.
            logger.exception("Failed to write audit log entry for %s", action_type)

    def log_action(self, user_id: str, action_type: str, resource_id: str = "",
                   details: Optional[Dict] = None) -> None:
        """Public wrapper so pages can record noteworthy actions."""
        self._log_action(user_id, action_type, resource_id, details or {})

    def get_audit_log(self, user_id: Optional[str] = None,
                      action_type: Optional[str] = None,
                      limit: int = 500) -> List[Dict]:
        query = "SELECT * FROM audit_log WHERE 1 = 1"
        params: List[Any] = []
        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)
        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            {
                "id": f"log_{r['id']:05d}",
                "user_id": r["user_id"],
                "action_type": r["action_type"],
                "resource_id": r["resource_id"],
                "details": serialization.loads(r["details"]) if r["details"] else {},
                "timestamp": r["timestamp"],
            }
            for r in rows
        ]
