"""Client for sending logs to Loki using simple POST requests."""

import json
import logging
from traceback import print_tb

import requests
from typing import List, Dict, Tuple, Optional


class LokiClient:
    """Client for sending logs to Loki."""

    def __init__(self, loki_url: str = None):
        """Initialize the Loki client.

        Args:
            loki_url: URL of the Loki server
        """
        self.loki_url = loki_url or "http://grafana-loki:3100/loki/api/v1/push"
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Initialized Loki client with URL: {self.loki_url}")

    def send_logs(
        self,
        app_name: str,
        service_name: str,
        log_entries: List[Tuple],
        extra_labels: Optional[Dict] = None,
    ) -> bool:
        """Send logs to Loki.

        Args:
            app_name: Name of the application
            service_name: Name of the service
            log_entries: List of log entries in format (timestamp, line, metadata)
            extra_labels: Additional labels to add to the logs

        Returns:
            bool: True if logs were sent successfully, False otherwise
        """
        if not log_entries:
            return True

        labels = {"app": app_name, "service": service_name}
        if extra_labels:
            labels.update(extra_labels)

        formatted_entries = []
        for timestamp, line, metadata in log_entries:
            formatted_entries.append(
                [
                    timestamp,
                    line,
                    metadata,
                ]
            )

        payload = {"streams": [{"stream": labels, "values": formatted_entries}]}
        try:
            response = requests.post(
                self.loki_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            return True

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send logs to Loki: {str(e)}")
            return False

    def close(self):
        pass
