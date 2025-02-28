"""File-based log monitor implementation with proper encoding support."""

import os
import glob
import time
from typing import Optional

from pygtail import Pygtail

from ..models import LogEntry
from .base import Monitor
from ..extractors import RegexExtractor


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

                try:
                    # Create Pygtail instance with UTF-8 encoding
                    new_lines = Pygtail(
                        file_path,
                        offset_file=offset_file,
                        encoding="utf-8",  # Only pass encoding, not errors
                    )

                    for line in new_lines:
                        line = line.strip()
                        if not line:
                            continue
                        entry = LogEntry(line, self.extractor)
                        log_entries.append(entry.to_loki_format())

                except UnicodeDecodeError:
                    # If UTF-8 fails, try with latin-1 which accepts any byte value
                    try:
                        self.logger.warning(
                            f"UTF-8 decoding failed for {file_path}, trying with latin-1"
                        )
                        new_lines = Pygtail(
                            file_path, offset_file=offset_file, encoding="latin-1"
                        )

                        for line in new_lines:
                            line = line.strip()
                            if not line:
                                continue
                            entry = LogEntry(line, self.extractor)
                            log_entries.append(entry.to_loki_format())

                    except Exception as e:
                        self.logger.error(
                            f"Error processing file {file_path} with fallback encoding: {e}",
                            exc_info=True,
                        )

                except Exception as e:
                    self.logger.error(
                        f"Error processing file {file_path}: {e}", exc_info=True
                    )

            if log_entries:
                self.send_logs(log_entries)
            time.sleep(self.poll_interval)
