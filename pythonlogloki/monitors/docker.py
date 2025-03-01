"""Docker container log monitor implementation."""

from dataclasses import dataclass
from typing import Optional, List, Iterator, Tuple
import logging
import os
import time
import requests
from ..models import LogEntry
from .base import Monitor
from ..extractors import RegexExtractor
from ..utils import ensure_dir, ThreadSafeOffsetStore

# Configuration Constants
DEFAULT_POLL_INTERVAL = 5
REQUEST_TIMEOUT = 2
RETRY_DELAY = 0.1
BATCH_FLUSH_CHECK = 1.0


class DockerAPIError(Exception):
    """Base exception for Docker API related errors."""

    pass


class DockerConnectionError(DockerAPIError):
    """Exception raised when connection to Docker API fails."""

    pass


@dataclass
class DockerLogConfig:
    """Configuration for Docker log fetching."""

    stdout: bool = True
    stderr: bool = True
    follow: bool = True
    tail: int = 0


class DockerAPIClient:
    """Handles communication with Docker API."""

    def __init__(self, host: str, port: int):
        self.base_url = f"http://{host}:{port}"
        self.logger = logging.getLogger(self.__class__.__name__)

    def get_container_logs(
        self, container_name: str, since: str, config: DockerLogConfig
    ) -> requests.Response:
        """Fetch container logs from Docker API."""
        url = (
            f"{self.base_url}/containers/{container_name}/logs?"
            f"stdout={int(config.stdout)}&stderr={int(config.stderr)}"
            f"&follow={int(config.follow)}&tail={config.tail}&since={since}"
        )

        try:
            response = requests.get(url, stream=True, timeout=REQUEST_TIMEOUT)
            if response.status_code != 200:
                raise DockerAPIError(
                    f"Failed to fetch logs: HTTP {response.status_code}"
                )
            return response
        except requests.Timeout:
            raise DockerConnectionError("Request timed out")
        except requests.RequestException as e:
            raise DockerConnectionError(f"Error connecting to Docker API: {e}")


class DockerAPIMonitor(Monitor):
    """Monitors Docker container logs via API."""

    def __init__(
        self,
        app_name: str,
        service_name: str,
        container_name: str,
        proxy_host: str,
        proxy_port: int,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
        extractor: Optional[RegexExtractor] = None,
        offset_dir: Optional[str] = None,
    ):
        super().__init__(app_name, service_name, poll_interval, extractor)
        self.container_name = container_name
        self.docker_client = DockerAPIClient(proxy_host, proxy_port)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._setup_offset_storage(offset_dir)

    def _setup_offset_storage(self, offset_dir: Optional[str]) -> None:
        """Initialize offset storage for tracking log position."""
        self.offset_dir = offset_dir
        if self.offset_dir:
            ensure_dir(self.offset_dir)
            offset_db_path = os.path.join(
                self.offset_dir, f"{self.safe_app_name}_{self.container_name}.offset.db"
            )
            self.offset_store = ThreadSafeOffsetStore(offset_db_path)

    def _read_offset(self) -> str:
        """Read last processed timestamp from database."""
        if hasattr(self, "offset_store"):
            return self.offset_store.read_offset()
        return str(int(time.time()))

    def _write_offset(self, ts: int) -> None:
        """Write the last processed timestamp to database."""
        if hasattr(self, "offset_store"):
            self.offset_store.write_offset(ts)

    def _process_log_line(self, line: str) -> Tuple[LogEntry, int]:
        """Process a single log line and return entry with timestamp."""
        line = line.strip()
        if not line:
            return None

        entry = LogEntry(line, self.extractor)
        ts_seconds = int(entry.timestamp_ns / 1_000_000_000)
        return entry, ts_seconds

    def _process_log_batch(
        self, lines: Iterator[str], last_flush: float
    ) -> Tuple[List[LogEntry], int, float]:
        """Process a batch of log lines."""
        buffer = []
        max_ts = None

        for line in lines:
            if not self._running:
                break

            result = self._process_log_line(line)
            if not result:
                continue

            entry, ts_seconds = result
            max_ts = max(ts_seconds, max_ts or 0)
            buffer.append(entry.to_loki_format())

            # Flush logs if enough time has passed
            current_time = time.time()
            if current_time - last_flush >= self.poll_interval and buffer:
                return buffer, max_ts, current_time

        return buffer, max_ts, last_flush

    def poll_logs(self) -> None:
        """Fetch logs from Docker API and process them in batches."""
        while self._running:
            try:
                last_offset = self._read_offset()
                config = DockerLogConfig()

                with self.docker_client.get_container_logs(
                    self.container_name, last_offset, config
                ) as resp:
                    buffer, max_ts = [], None
                    last_flush = time.time()

                    buffer, max_ts, last_flush = self._process_log_batch(
                        resp.iter_lines(decode_unicode=True), last_flush
                    )

                    if buffer:
                        self.send_logs(
                            buffer, extra_labels={"container": self.container_name}
                        )
                        if max_ts:
                            self._write_offset(max_ts)

            except DockerConnectionError as e:
                if self._running:
                    self.logger.debug(f"Connection issue: {e}")
                time.sleep(RETRY_DELAY)

            except DockerAPIError as e:
                self.logger.error(str(e))
                time.sleep(self.poll_interval)

            except Exception as e:
                self.logger.error(f"Error in DockerAPIMonitor: {e}", exc_info=True)
                time.sleep(self.poll_interval)
