"""Extractors for parsing log entries."""

import re
import datetime
from typing import Optional


class RegexExtractor:
    """Extracts timestamps and log levels from log lines using regular expressions."""

    def __init__(
        self,
        timestamp_regex: str = r"^([^|]+)",
        log_level_regex: str = r"^[^|]+\|([^|]+)\|",
    ):
        self.timestamp_pattern = re.compile(timestamp_regex)
        self.log_level_pattern = re.compile(log_level_regex)

    def extract_timestamp(self, line: str) -> Optional[float]:
        """Extract timestamp from a log line and return as Unix epoch in seconds."""
        match = self.timestamp_pattern.match(line)
        if not match:
            return None

        timestamp_str = match.group(1).strip()
        try:
            # Handle fractional seconds with proper padding
            if "." in timestamp_str:
                date_part, time_part = timestamp_str.split(" ")
                time_whole, time_frac = time_part.split(".")
                # Pad the fractional part to 6 digits for microseconds
                time_frac = time_frac.ljust(6, "0")
                timestamp_str = f"{date_part} {time_whole}.{time_frac}"

            return datetime.datetime.strptime(
                timestamp_str, "%Y-%m-%d %H:%M:%S.%f"
            ).timestamp()
        except ValueError:
            # Try parsing without microseconds
            try:
                return datetime.datetime.strptime(
                    timestamp_str, "%Y-%m-%d %H:%M:%S"
                ).timestamp()
            except ValueError:
                return None

    def extract_log_level(self, line: str) -> str:
        """Extract log level from a log line."""
        match = self.log_level_pattern.match(line)
        return match.group(1).strip().lower() if match else "unknown"
