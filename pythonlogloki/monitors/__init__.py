"""Monitor implementations for different log sources."""

from .base import Monitor
from .file import FileMonitor
from .docker import DockerAPIMonitor

# Dictionary of available monitor types
MONITOR_TYPES = {
    "FileMonitor": FileMonitor,
    "DockerAPIMonitor": DockerAPIMonitor,
}

__all__ = ["Monitor", "FileMonitor", "DockerAPIMonitor", "MONITOR_TYPES"]
