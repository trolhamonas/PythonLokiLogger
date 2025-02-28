"""Docker container log monitor implementation."""

import logging
import os
import time
import requests
from typing import Optional

from ..models import LogEntry
from .base import Monitor
from ..extractors import RegexExtractor
from ..utils import ensure_dir, ThreadSafeOffsetStore


class DockerAPIMonitor(Monitor):
    """Monitors Docker container logs via API."""

    def __init__(
        self,
        app_name: str,
        service_name: str,
        container_name: str,
        proxy_host: str,
        proxy_port: int,
        poll_interval: int = 5,
        extractor: Optional[RegexExtractor] = None,
        offset_dir: Optional[str] = None,
    ):
        super().__init__(app_name, service_name, poll_interval, extractor)
        self.container_name = container_name
        self.base_url = f"http://{proxy_host}:{proxy_port}"
        self.logger = logging.getLogger(self.__class__.__name__)

        # Setup offset storage
        self.offset_dir = offset_dir
        if self.offset_dir:
            ensure_dir(self.offset_dir)
            offset_db_path = os.path.join(
                self.offset_dir, f"{self.safe_app_name}_{self.container_name}.offset.db"
            )
            self.offset_store = ThreadSafeOffsetStore(offset_db_path)

        # Setup HTTP session with connection pooling
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=100, max_retries=3
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _read_offset(self) -> str:
        """Read last processed timestamp from database."""
        if hasattr(self, "offset_store"):
            return self.offset_store.read_offset()
        return str(int(time.time()))

    def _write_offset(self, ts: int) -> None:
        """Write the last processed timestamp to database."""
        if hasattr(self, "offset_store"):
            self.offset_store.write_offset(ts)

    def poll_logs(self) -> None:
        """Fetch logs from Docker API and process them in batches."""
        while self._running:
            try:
                last_offset = self._read_offset()
                url = (
                    f"{self.base_url}/containers/{self.container_name}/logs?"
                    f"stdout=1&stderr=1&follow=1&tail=0&since={last_offset}"
                )

                # Add timeout to the request to make it interruptible
                with self.session.get(url, stream=True, timeout=2) as resp:
                    if resp.status_code != 200:
                        self.logger.error(
                            f"Failed to fetch logs: HTTP {resp.status_code}"
                        )
                        time.sleep(self.poll_interval)
                        continue

                    buffer, max_ts = [], None
                    last_flush = time.time()

                    for line in resp.iter_lines(decode_unicode=True):
                        if not self._running:
                            break

                        # Check _running status periodically
                        if not line and not self._running:
                            break

                        line = line.strip() if line else ""
                        if not line:
                            continue

                        entry = LogEntry(line, self.extractor)
                        ts_seconds = int(entry.timestamp_ns / 1_000_000_000)
                        max_ts = max(ts_seconds, max_ts or 0)

                        buffer.append(entry.to_loki_format())

                        # Flush logs if enough time has passed
                        if time.time() - last_flush >= self.poll_interval and buffer:
                            self.send_logs(
                                buffer, extra_labels={"container": self.container_name}
                            )
                            if max_ts:
                                self._write_offset(max_ts)
                            buffer.clear()
                            last_flush = time.time()

            # Handle request timeouts gracefully
            except requests.Timeout:
                if self._running:  # Only log if not intentionally stopping
                    self.logger.debug("Request timed out, reconnecting...")
                time.sleep(0.1)  # Brief pause before retry

            except requests.RequestException as e:
                self.logger.error(f"Error connecting to Docker API: {e}")
                time.sleep(self.poll_interval)

            except Exception as e:
                self.logger.error(f"Error in DockerAPIMonitor: {e}", exc_info=True)
                time.sleep(self.poll_interval)

    def __del__(self):
        """Clean up resources."""
        super().__del__()
        if hasattr(self, "session"):
            try:
                self.session.close()
            except:
                pass
