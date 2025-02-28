"""Clients for handling logs with correctly formatted JSON for Loki."""

import json
from typing import List, Dict, Tuple, Optional


class LokiClient:
    """Test client that prints logs and displays the correctly formatted JSON for Loki."""

    def __init__(self, loki_url: str = None):
        """Initialize the test client."""
        self.loki_url = loki_url or "http://localhost:3100/loki/api/v1/push"
        print(
            f"TEST LOKI CLIENT: Logs will be printed instead of sent to {self.loki_url}"
        )

    def send_logs(
        self,
        app_name: str,
        service_name: str,
        log_entries: List[Tuple],
        extra_labels: Optional[Dict] = None,
    ) -> bool:
        """Print logs and the JSON that would have been sent to Loki.

        Args:
            app_name: Name of the application
            service_name: Name of the service
            log_entries: List of log entries in format (timestamp, line, metadata)
            extra_labels: Additional labels to add to the logs
        """
        if not log_entries:
            return True

        # Print a separator for better readability
        print("\n" + "=" * 80)
        print(f"LOGS FROM: {app_name}/{service_name}")
        print("-" * 80)

        # Print each log entry in a readable format
        for timestamp, line, metadata in log_entries:
            level = metadata.get("level", "info").upper()
            print(f"[{level}] {line}")

        # Prepare labels dictionary
        labels = {"app": app_name, "service": service_name}
        if extra_labels:
            labels.update(extra_labels)

        # Format the entries correctly with metadata as the third element
        formatted_entries = []
        for timestamp, line, metadata in log_entries:
            # Keep the level in the metadata object
            formatted_entries.append(
                [
                    timestamp,  # Timestamp in nanoseconds
                    line,  # The log line text
                    metadata,  # Metadata object containing level
                ]
            )

        # Create the Loki-compatible payload
        streams = [{"stream": labels, "values": formatted_entries}]

        payload = {"streams": streams}

        # Print the JSON payload that would be sent to Loki
        print("\nLOKI JSON PAYLOAD:")
        print("-" * 80)
        print(json.dumps(payload, indent=2))
        print("=" * 80)

        return True

    def close(self):
        """No-op for test client."""
        pass
