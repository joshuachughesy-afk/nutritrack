"""Logging and diagnostics for bug reports.

Everything goes to a small rotating log file in the app's private storage (`logs/nutritrack.log`, 3 × 256 KB):
app start-up, every unhandled error with its traceback (including Flet event-handler errors), and failed background
work such as notification scheduling or online lookups. Profile → About & diagnostics shows the recent log and copies
a report you can paste into a GitHub issue. Nothing is sent anywhere automatically.
"""
from __future__ import annotations

import logging
import os
import platform
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__

log = logging.getLogger("nutritrack")
_handler: RotatingFileHandler | None = None


def log_dir() -> Path:
    base = os.getenv("FLET_APP_STORAGE_DATA") or os.path.join(Path.home(), ".nutritrack")
    path = Path(base) / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_file() -> Path:
    return log_dir() / "nutritrack.log"


def setup_logging(level: int = logging.INFO) -> None:
    """Idempotent: attach the rotating file handler to our logger and to Flet's (errors only)."""
    global _handler
    if _handler is not None:
        return
    _handler = RotatingFileHandler(log_file(), maxBytes=256 * 1024, backupCount=3, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(_handler)
    log.setLevel(level)
    flet_errors = logging.getLogger("flet")
    flet_errors.addHandler(_handler)  # Flet logs handler exceptions here with full tracebacks
    if flet_errors.level == logging.NOTSET or flet_errors.level > logging.ERROR:
        flet_errors.setLevel(logging.ERROR)


def tail(lines: int = 40) -> str:
    try:
        text = log_file().read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return "(no log yet)"
    return "\n".join(text[-lines:])


def environment(page=None) -> dict[str, str]:
    import flet

    info = {
        "NutriTrack": __version__,
        "Flet": getattr(flet, "__version__", None) or getattr(getattr(flet, "version", None), "version", "?"),
        "Python": sys.version.split()[0],
        "OS": f"{platform.system()} {platform.release()}",
    }
    if page is not None:
        info["Platform"] = str(getattr(getattr(page, "platform", None), "value", "?"))
        info["Web"] = str(bool(getattr(page, "web", False)))
    return info


def report(store, page=None, lines: int = 60) -> str:
    """Plain-text bug report: versions, data counts (no personal values) and the recent log."""
    env = environment(page)
    counts = {}
    for table in ("entries", "water", "doses", "supplements", "custom_foods", "days"):
        try:
            counts[table] = store.conn.execute(f"select count(*) from {table}").fetchone()[0]
        except Exception:
            counts[table] = "?"
    parts = ["## Environment", *[f"- {k}: {v}" for k, v in env.items()],
             "## Data (counts only)", *[f"- {k}: {v}" for k, v in counts.items()],
             f"## Recent log ({lines} lines)", "```", tail(lines), "```"]
    return "\n".join(parts)
