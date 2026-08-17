"""
Runtime diagnostics.

Two blind spots made the reported "page goes blank / keeps reconnecting"
problem impossible to diagnose:

1. Unhandled exceptions raised inside a page script are caught by Streamlit
   itself, not by ``report_error()``, so they never reached ``app.log``.
   Combined with ``client.showErrorDetails = "none"`` (deliberate production
   hardening) nothing anywhere recorded the cause.

2. Nothing recorded script runs or session identity, so a websocket that
   drops and reconnects — which presents as a blank page — was
   indistinguishable from an idle app.

This module closes both. It only observes; it never changes what the user is
shown, so ``showErrorDetails`` stays at ``"none"``.
"""

import threading
import time
import traceback
from contextlib import contextmanager
from typing import Optional

from src.logging_config import get_logger

logger = get_logger("diagnostics")

_install_lock = threading.Lock()
_installed = False
_seen_sessions: set = set()

#: The page currently executing on this thread. Streamlit runs each script run
#: on its own thread, so thread-local storage keeps concurrent sessions from
#: mislabelling each other's runs.
_current = threading.local()


def install_crash_logging() -> None:
    """
    Record unhandled page exceptions in ``instance/logs/app.log``.

    Streamlit calls ``handle_uncaught_app_exception`` for any error escaping a
    page script. ``exec_code`` imports that function by name, so the binding in
    *that* module is what has to be replaced — patching ``error_util`` alone
    would have no effect.

    Idempotent and defensive: diagnostics must never be the reason the app
    fails to start, so an unexpected Streamlit layout is logged and ignored.
    """
    global _installed
    with _install_lock:
        if _installed:
            return
        _installed = True

        try:
            from streamlit import error_util
            from streamlit.runtime.scriptrunner import exec_code
        except Exception as exc:  # noqa: BLE001 - never block startup
            logger.warning("Crash logging unavailable: %s", exc)
            return

        original = error_util.handle_uncaught_app_exception

        def logging_handler(ex: BaseException) -> None:
            try:
                logger.error(
                    "Unhandled exception in page script (session=%s, page=%s)\n%s",
                    _session_id() or "unknown",
                    _page_name() or "unknown",
                    "".join(traceback.format_exception(
                        type(ex), ex, ex.__traceback__)),
                )
            except Exception:  # noqa: BLE001 - logging must not mask the error
                pass
            original(ex)

        patched = []
        for module in (error_util, exec_code):
            if getattr(module, "handle_uncaught_app_exception", None) is not None:
                module.handle_uncaught_app_exception = logging_handler
                patched.append(module.__name__)

        try:
            from streamlit.runtime import fragment as _fragment
            if getattr(_fragment, "handle_uncaught_app_exception", None) is not None:
                _fragment.handle_uncaught_app_exception = logging_handler
                patched.append(_fragment.__name__)
        except Exception:  # noqa: BLE001
            pass

        logger.info("Crash logging installed on: %s", ", ".join(patched))
        _install_run_timing()
        _install_session_logging()


def _install_session_logging() -> None:
    """
    Record when a session is shut down.

    A browser whose websocket drops leaves the server tearing the session down:
    the in-flight script is stopped and no further runs are scheduled. From the
    log that is indistinguishable from a hang unless the shutdown itself is
    recorded, so this marks it explicitly.
    """
    try:
        from streamlit.runtime.app_session import AppSession
    except Exception as exc:  # noqa: BLE001
        logger.warning("Session logging unavailable: %s", exc)
        return

    original = AppSession.shutdown

    def logging_shutdown(self) -> None:
        try:
            logger.warning("Session SHUTDOWN: %s", str(getattr(self, "id", "?"))[:8])
        except Exception:  # noqa: BLE001
            pass
        return original(self)

    AppSession.shutdown = logging_shutdown
    logger.info("Session logging installed on streamlit.runtime.app_session")


def _install_run_timing() -> None:
    """
    Time every script run from start to finish.

    ``log_page_run`` records only that a page *started*. Streamlit runs one
    script at a time per session, so a run that never finishes blocks every
    later navigation — the user clicks another page and nothing happens. That
    is invisible without a matching "finished" record, which is what this adds.

    ``script_runner`` imports ``exec_func_with_error_handling`` by name, so the
    binding in that module is the one that has to be replaced.
    """
    try:
        from streamlit.runtime.scriptrunner import script_runner
    except Exception as exc:  # noqa: BLE001 - never block startup
        logger.warning("Run timing unavailable: %s", exc)
        return

    original = getattr(script_runner, "exec_func_with_error_handling", None)
    if original is None:
        logger.warning("Run timing unavailable: entry point not found")
        return

    def timing_wrapper(*args, **kwargs):
        started = time.perf_counter()
        # The page name is set by inject_css() *during* the run, so it is only
        # meaningful once the run is over.
        _current.page = None

        # Identify the run from Streamlit's own context instead. inject_css()
        # runs after the page's imports, so a run that dies while importing has
        # no name of its own - which is exactly the case worth diagnosing.
        script = _script_for_run(args, kwargs)
        logger.info("Script run START: %s", script)
        try:
            result = original(*args, **kwargs)
        except BaseException as exc:
            logger.error("Script run ABORTED after %.2fs (page=%s): %s: %s",
                         time.perf_counter() - started,
                         getattr(_current, "page", None) or "?",
                         type(exc).__name__, exc)
            raise
        elapsed = time.perf_counter() - started
        page = getattr(_current, "page", None) or "?"
        try:
            _, run_without_errors, _, premature_stop, _ = result
            outcome = (
                "ok" if run_without_errors and not premature_stop
                else "stopped-early" if run_without_errors
                else "error"
            )
        except Exception:  # noqa: BLE001 - tolerate a changed return shape
            outcome = "unknown"
        level = logger.warning if elapsed >= 5.0 else logger.info
        level("Script run FINISHED: %s [%s] in %.2fs (%s)",
              page, script, elapsed, outcome)
        return result

    script_runner.exec_func_with_error_handling = timing_wrapper
    logger.info("Run timing installed on streamlit.runtime.scriptrunner.script_runner")


def _script_for_run(args, kwargs) -> str:
    """
    Best-effort name of the script a run is executing.

    Reads the ScriptRunContext passed to ``exec_func_with_error_handling``,
    falling back to the ambient context. Purely diagnostic, so every lookup is
    guarded — a changed Streamlit internal must not break the app.
    """
    ctx = kwargs.get("ctx")
    if ctx is None:
        for arg in args:
            if hasattr(arg, "pages_manager") or hasattr(arg, "main_script_path"):
                ctx = arg
                break
    if ctx is None:
        ctx = _ctx()
    if ctx is None:
        return "unknown"

    try:
        pages = ctx.pages_manager
        page_hash = pages.current_page_script_hash
        for entry in (pages.get_pages() or {}).values():
            if entry.get("page_script_hash") == page_hash:
                return (entry.get("page_name")
                        or _basename(entry.get("script_path"))
                        or page_hash)
        intended = pages.intended_page_name
        if intended:
            return f"{intended} (intended)"
    except Exception:  # noqa: BLE001
        pass

    return _basename(getattr(ctx, "main_script_path", None)) or "unknown"


def _basename(path) -> str:
    if not path:
        return ""
    return str(path).replace("\\", "/").rsplit("/", 1)[-1]


def _ctx():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        return get_script_run_ctx()
    except Exception:  # noqa: BLE001
        return None


def _session_id() -> Optional[str]:
    ctx = _ctx()
    return getattr(ctx, "session_id", None) if ctx else None


def _page_name() -> Optional[str]:
    ctx = _ctx()
    if not ctx:
        return None
    for attr in ("page_script_hash", "main_script_path"):
        value = getattr(ctx, attr, None)
        if value:
            return str(value)
    return None


def log_page_run(page: str) -> None:
    """
    Record that a page script ran, and note the first run of each session.

    A websocket that keeps dropping shows up here as a stream of *new* session
    ids for the same user: the browser reconnects, Streamlit issues a fresh
    session, and the page starts over. A healthy app reuses one session id
    across many page runs.
    """
    session = _session_id()
    if session and session not in _seen_sessions:
        _seen_sessions.add(session)
        logger.info(
            "New Streamlit session %s (sessions seen this process: %d)",
            session, len(_seen_sessions),
        )
    # INFO, not DEBUG: a page that starts and never finishes is the signature of
    # a hang, and that is invisible if these records are filtered out.
    _current.page = page
    logger.info("Page run START: %s (session=%s)", page, _short(session))


def _short(session: Optional[str]) -> str:
    return (session or "unknown")[:8]


@contextmanager
def timed(label: str, warn_after: float = 1.0):
    """
    Time a step and record how long it took.

    Anything slower than ``warn_after`` is logged at WARNING so slow steps stand
    out; a step that never completes leaves only its "start" line, which is
    exactly how a hang is identified after the fact.
    """
    logger.info("STEP start: %s", label)
    started = time.perf_counter()
    try:
        yield
    except BaseException as exc:
        logger.error("STEP failed after %.2fs: %s (%s: %s)",
                     time.perf_counter() - started, label,
                     type(exc).__name__, exc)
        raise
    else:
        elapsed = time.perf_counter() - started
        if elapsed >= warn_after:
            logger.warning("STEP slow: %s took %.2fs", label, elapsed)
        else:
            logger.info("STEP done: %s (%.2fs)", label, elapsed)
