"""Base abstract class for all log monitors."""

import logging
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional

from ..extractors import RegexExtractor
from ..clients import LokiClient


class Monitor(ABC):
    """Base abstract class for all log monitors."""

    def __init__(
        self,
        app_name: str,
        service_name: str,
        poll_interval: int = 5,
        extractor: Optional[RegexExtractor] = None,
    ):
        self.app_name = app_name
        self.safe_app_name = app_name.replace(" ", "_")
        self.service_name = service_name
        self.poll_interval = poll_interval
        self.extractor = extractor or RegexExtractor()
        self.loki_client = LokiClient()
        self._running = False
        self.logger = logging.getLogger(f"{self.__class__.__name__}.{self.app_name}")

    @abstractmethod
    def poll_logs(self) -> None:
        """Poll for new log entries (implemented by subclasses)."""
        pass

    def start(self) -> None:
        """Start the monitoring process."""
        self._running = True
        self.logger.info(
            f"Starting monitor for '{self.app_name}' with service '{self.service_name}'"
        )
        try:
            self.poll_logs()
        except Exception as e:
            self.logger.error(f"Error in monitor {self.app_name}: {e}", exc_info=True)
        finally:
            self._running = False

    def stop(self) -> None:
        """Stop the monitoring process."""
        self._running = False

    def send_logs(
        self, log_entries: List[Tuple], extra_labels: Optional[Dict] = None
    ) -> None:
        """Send collected log entries to Loki."""
        if log_entries:
            self.loki_client.send_logs(
                self.app_name, self.service_name, log_entries, extra_labels
            )

    def __del__(self):
        """Ensure resources are cleaned up."""
        if hasattr(self, "loki_client"):
            try:
                self.loki_client.close()
            except:
                pass
