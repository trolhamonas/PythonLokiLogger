"""Utility functions and helper classes for log monitoring."""

from typing import Optional, Any
import os
import threading
import shelve
import time
import logging
from contextlib import contextmanager


class OffsetStoreError(Exception):
    """Base exception for offset store operations."""

    pass


class DirectoryError(Exception):
    """Exception raised when directory operations fail."""

    pass


def ensure_dir(directory: str) -> None:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory: Path to the directory to create

    Raises:
        DirectoryError: If directory creation fails
    """
    try:
        os.makedirs(directory, exist_ok=True)
    except Exception as e:
        raise DirectoryError(f"Failed to create directory {directory}: {e}")


class ThreadSafeDB:
    """Thread-safe wrapper for shelve database operations."""

    def __init__(self, db_path: str):
        """
        Initialize the database wrapper.

        Args:
            db_path: Path to the shelve database file
        """
        self.db_path = db_path
        self.lock = threading.Lock()
        self.logger = logging.getLogger(self.__class__.__name__)

    @contextmanager
    def _open_db(self):
        """
        Context manager for safe database operations.

        Yields:
            shelve.DbfilenameShelf: Opened database object

        Raises:
            OffsetStoreError: If database operations fail
        """
        try:
            with self.lock:
                db = shelve.open(self.db_path)
                try:
                    yield db
                finally:
                    db.close()
        except Exception as e:
            raise OffsetStoreError(f"Database operation failed: {e}")

    def read(self, key: str, default: Any = None) -> Any:
        """
        Read a value from the database.

        Args:
            key: Key to read
            default: Default value if key doesn't exist

        Returns:
            Value associated with the key or default

        Raises:
            OffsetStoreError: If read operation fails
        """
        try:
            with self._open_db() as db:
                return db.get(key, default)
        except Exception as e:
            self.logger.error(f"Failed to read from database: {e}")
            return default

    def write(self, key: str, value: Any) -> None:
        """
        Write a value to the database.

        Args:
            key: Key to write
            value: Value to store

        Raises:
            OffsetStoreError: If write operation fails
        """
        try:
            with self._open_db() as db:
                db[key] = value
        except Exception as e:
            self.logger.error(f"Failed to write to database: {e}")
            raise OffsetStoreError(f"Failed to write to database: {e}")


class ThreadSafeOffsetStore:
    """Thread-safe store for Docker log offsets."""

    OFFSET_KEY = "last_offset"

    def __init__(self, db_path: str):
        """
        Initialize the offset store.

        Args:
            db_path: Path to the offset database file
        """
        self.db = ThreadSafeDB(db_path)
        self.logger = logging.getLogger(self.__class__.__name__)

    def read_offset(self) -> str:
        """
        Read last processed timestamp from database.

        Returns:
            str: Last processed timestamp or current time if not found
        """
        try:
            current_time = str(int(time.time()))
            return self.db.read(self.OFFSET_KEY, current_time)
        except Exception as e:
            self.logger.warning(f"Failed to read offset, using current time: {e}")
            return str(int(time.time()))

    def write_offset(self, timestamp: int) -> None:
        """
        Write the last processed timestamp to database.

        Args:
            timestamp: Unix timestamp to store

        Raises:
            OffsetStoreError: If write operation fails
        """
        try:
            self.db.write(self.OFFSET_KEY, str(timestamp))
        except Exception as e:
            self.logger.error(f"Failed to write offset: {e}")
            raise OffsetStoreError(f"Failed to write offset: {e}")
