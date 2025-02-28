import builtins
import os
import glob
import time
from typing import Optional

from pygtail import Pygtail

from ..models import LogEntry
from .base import Monitor
from ..extractors import RegexExtractor

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


class FileMonitor(Monitor):
    """Monitors log files in a directory for new entries."""

    def __init__(
        self,
        app_name: str,
        service_name: str,
        folder: str,
        poll_interval: int = 5,
        extractor: Optional[RegexExtractor] = None,
        offset_dir: Optional[str] = None,
    ):
        super().__init__(app_name, service_name, poll_interval, extractor)
        self.folder = folder
        self.offset_dir = offset_dir

    def poll_logs(self) -> None:
        """Poll log files and process new lines."""
        while self._running:
            log_entries = []
            files = glob.glob(os.path.join(self.folder, "*.txt")) + glob.glob(
                os.path.join(self.folder, "*.log")
            )

            for file_path in files:
                log_filename = os.path.basename(file_path)
                offset_file = (
                    os.path.join(
                        self.offset_dir, f"{self.safe_app_name}_{log_filename}.offset"
                    )
                    if self.offset_dir
                    else None
                )

                # Use Pygtail without specifying encoding; our monkey patch ensures UTF-8.
                new_lines = Pygtail(file_path, offset_file=offset_file)
                for line in new_lines:
                    line = line.strip()
                    if line:
                        entry = LogEntry(line, self.extractor)
                        log_entries.append(entry.to_loki_format())

            if log_entries:
                self.send_logs(log_entries)
            time.sleep(self.poll_interval)
