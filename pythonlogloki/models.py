"""Data models for log processing."""

import time
from typing import Tuple, Dict


class LogEntry:
    """Represents a structured log entry with timestamp, content, and metadata."""

    def __init__(self, line: str, extractor):
        self.line = line.strip()
        self.timestamp = extractor.extract_timestamp(line)
        self.level = extractor.extract_log_level(line)
        self.timestamp_ns = (
            int(self.timestamp * 1_000_000_000)
            if self.timestamp
            else int(time.time() * 1_000_000_000)
        )

    def to_loki_format(self) -> Tuple[str, str, Dict[str, str]]:
        """Convert to format expected by Loki: (timestamp, line, metadata)."""
        return str(self.timestamp_ns), self.line, {"level": self.level}
