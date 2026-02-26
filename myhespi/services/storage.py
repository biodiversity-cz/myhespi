from __future__ import annotations

import json
import re
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

_JOB_ID_RE = re.compile(r"^[a-f0-9-]{8,64}$")

_last_cleanup_time: float = 0.0
_cleanup_lock = threading.Lock()
_CLEANUP_INTERVAL_SECONDS = 3600  # 60 minut


def ensure_temp_root(temp_root: Path) -> None:
    temp_root.mkdir(parents=True, exist_ok=True)


def new_job_id() -> str:
    return str(uuid.uuid4())


def get_job_dir(temp_root: Path, job_id: str) -> Path:
    if not _JOB_ID_RE.match(job_id):
        raise ValueError("Invalid job id.")
    return temp_root / job_id


def safe_job_file(job_dir: Path, filename: str) -> Path:
    target = (job_dir / filename).resolve()
    if not str(target).startswith(str(job_dir.resolve())):
        raise ValueError("Invalid file path.")
    return target


def save_result(job_dir: Path, payload: dict) -> None:
    result_path = job_dir / "result.json"
    result_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_result(job_dir: Path) -> dict:
    result_path = job_dir / "result.json"
    if not result_path.exists():
        raise FileNotFoundError("Result not found.")
    return json.loads(result_path.read_text(encoding="utf-8"))


def maybe_cleanup(temp_root: Path, retention_days: int) -> None:
    """Run cleanup at most once per *_CLEANUP_INTERVAL_SECONDS*."""
    global _last_cleanup_time

    if retention_days < 1:
        return

    now = time.monotonic()
    if now - _last_cleanup_time < _CLEANUP_INTERVAL_SECONDS:
        return

    with _cleanup_lock:
        if now - _last_cleanup_time < _CLEANUP_INTERVAL_SECONDS:
            return
        _cleanup_old_jobs(temp_root, retention_days)
        _last_cleanup_time = time.monotonic()


def _cleanup_old_jobs(temp_root: Path, retention_days: int) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for child in temp_root.iterdir():
        if not child.is_dir():
            continue
        try:
            mtime = datetime.fromtimestamp(child.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        if mtime < cutoff:
            shutil.rmtree(child, ignore_errors=True)
