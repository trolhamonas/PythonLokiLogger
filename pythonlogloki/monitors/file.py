"""File-based log monitor implementation."""

import builtins
import os
import glob
import time
import logging
from typing import Optional, List, Iterator

from pygtail import Pygtail

from ..models import LogEntry
from .base import Monitor
from ..extractors import RegexExtractor

# Configuration Constants
DEFAULT_POLL_INTERVAL = 5
LOG_FILE_PATTERNS = ["*.txt", "*.log"]

# Monkey-patch built-in open() to default to UTF-8 for text files.
_original_open = builtins.open


def open_utf8(
    file,
    mode="r",
    buffering=-1,
    encoding=None,
    errors=None,
    newline=None,
    closefd=True,
    opener=None,
):
    if "b" not in mode and encoding is None:
        encoding = "utf-8"
    return _original_open(
        file, mode, buffering, encoding, errors, newline, closefd, opener
    )


builtins.open = open_utf8


class FileMonitorError(Exception):
    """Base exception for file monitoring errors."""

    pass


class LogFileScanner:
    """Handles log file discovery and reading."""

    def __init__(
        self, folder: str, safe_app_name: str, offset_dir: Optional[str] = None
    ):
        self.folder = folder
        self.safe_app_name = safe_app_name
        self.offset_dir = offset_dir
        self.logger = logging.getLogger(self.__class__.__name__)

    def find_log_files(self) -> List[str]:
        """Find all log files in the configured folder."""
        log_files = []
        for pattern in LOG_FILE_PATTERNS:
            files = glob.glob(os.path.join(self.folder, pattern))
            log_files.extend(files)
        return log_files

    def get_offset_path(self, file_path: str) -> Optional[str]:
        """Generate offset file path for a given log file."""
        if not self.offset_dir:
            return None

        log_filename = os.path.basename(file_path)
        return os.path.join(
            self.offset_dir, f"{self.safe_app_name}_{log_filename}.offset"
        )

    def read_new_lines(
        self, file_path: str, offset_path: Optional[str]
    ) -> Iterator[str]:
        """Read new lines from a file using Pygtail."""
        try:
            return Pygtail(file_path, offset_file=offset_path)
        except Exception as e:
            self.logger.error(f"Error reading file {os.path.basename(file_path)}: {e}")
            return iter([])


class FileMonitor(Monitor):
    """Monitors log files in a directory for new entries."""

    def __init__(
        self,
        app_name: str,
        service_name: str,
        folder: str,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        extractor: Optional[RegexExtractor] = None,
        offset_dir: Optional[str] = None,
    ):
        super().__init__(app_name, service_name, poll_interval, extractor)
        self.scanner = LogFileScanner(folder, self.safe_app_name, offset_dir)
        self.logger = logging.getLogger(self.__class__.__name__)

    def _process_line(self, line: str) -> Optional[dict]:
        """Process a single log line."""
        line = line.strip()
        if not line:
            return None

        try:
            entry = LogEntry(line, self.extractor)
            return entry.to_loki_format()
        except Exception as e:
            self.logger.error(f"Error processing log line: {e}")
            return None

    def _process_file(self, file_path: str, offset_path: Optional[str]) -> List[dict]:
        """Process all new lines from a single file."""
        entries = []
        for line in self.scanner.read_new_lines(file_path, offset_path):
            if not self._running:
                break

            if entry := self._process_line(line):
                entries.append(entry)
        return entries

    def poll_logs(self) -> None:
        """Poll log files and process new lines."""
        while self._running:
            try:
                log_entries = []
                for file_path in self.scanner.find_log_files():
                    if not self._running:
                        break

                    offset_path = self.scanner.get_offset_path(file_path)
                    entries = self._process_file(file_path, offset_path)
                    log_entries.extend(entries)

                if log_entries:
                    self.send_logs(log_entries)

            except Exception as e:
                self.logger.error(f"Error in file monitoring: {e}")

            time.sleep(self.poll_interval)
