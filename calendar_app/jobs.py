"""Single-host cron lock, including SQLite; all commands share one lock."""

import fcntl
from contextlib import contextmanager
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError


@contextmanager
def job_lock():
    path = Path(settings.BASE_DIR) / "data" / "area3.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CommandError("Another Area 3 job is running; retry next tick.")
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
