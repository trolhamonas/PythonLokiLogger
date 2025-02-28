"""Utility functions and helper classes."""

import os
import threading
import shelve
import time


def ensure_dir(directory: str) -> None:
    """Ensure a directory exists, creating it if necessary."""
    os.makedirs(directory, exist_ok=True)


def safe_open(file, mode="r", *args, **kwargs):
    """Enhanced open function that defaults to UTF-8 with error replacement."""
    if "r" in mode:
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
    return open(file, mode, *args, **kwargs)


class ThreadSafeOffsetStore:
    """Thread-safe store for Docker log offsets."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.lock = threading.Lock()

    def read_offset(self) -> str:
        """Read last processed timestamp from database in a thread-safe manner."""
        with self.lock:
            with shelve.open(self.db_path) as db:
                return db.get("last_offset", str(int(time.time())))

    def write_offset(self, ts: int) -> None:
        """Write the last processed timestamp to database in a thread-safe manner."""
        with self.lock:
            with shelve.open(self.db_path) as db:
                db["last_offset"] = str(ts)
