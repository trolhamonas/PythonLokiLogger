"""Entry point for the log monitoring application."""

import os
import time
import json
import logging
import threading

# Now we can import from our package using absolute imports
from pythonlogloki.extractors import RegexExtractor
from pythonlogloki.monitors.base import Monitor
from pythonlogloki.monitors.file import FileMonitor
from pythonlogloki.monitors.docker import DockerAPIMonitor

# Get configuration path from environment variable with fallback
CONFIG_PATH = os.environ.get("CONFIG_PATH", "/config/monitors.json")
DATA_DIR = os.environ.get("DATA_DIR", "/config/data")

# Define paths for offset directories
PYGTAIL_DIR = os.path.join(DATA_DIR, "pygtail")
DOCKER_DIR = os.path.join(DATA_DIR, "docker")

# Print the paths for debugging
print(f"Using CONFIG_PATH: {CONFIG_PATH}")
print(f"Using DATA_DIR: {DATA_DIR}")
print(f"Using PYGTAIL_DIR: {PYGTAIL_DIR}")
print(f"Using DOCKER_DIR: {DOCKER_DIR}")


def setup_logging(log_level="INFO"):
    """Configure application logging."""
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    log_file = os.path.join(DATA_DIR, "log_monitor.log")

    try:
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(), logging.FileHandler(log_file)],
        )
    except Exception as e:
        print(f"Error setting up file logging: {e}")
        # Continue without file logging
        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler()],
        )


class MonitorManager:
    """Manages multiple monitor instances."""

    def __init__(self):
        self.monitors = []
        self.threads = []

    def add_monitor(self, monitor: Monitor) -> None:
        """Add a monitor to the manager."""
        self.monitors.append(monitor)

    def start_all(self) -> None:
        """Start all monitors in separate threads."""
        for monitor in self.monitors:
            thread = threading.Thread(target=monitor.start, daemon=True)
            thread.start()
            self.threads.append(thread)

    def stop_all(self) -> None:
        """Stop all monitors."""
        for monitor in self.monitors:
            monitor.stop()

    def wait_all(self, timeout=1.0) -> None:
        """Wait for all monitor threads to complete with timeout."""
        end_time = time.time() + timeout
        for thread in self.threads:
            remaining = max(0, end_time - time.time())
            thread.join(timeout=remaining)  # Join with timeout


def create_monitor_from_config(config):
    """Create a monitor instance from a configuration dictionary."""
    config_copy = config.copy()  # Create a copy to avoid modifying the original

    monitor_type = config_copy.pop("type", None)
    if not monitor_type:
        print("Missing monitor type in configuration")
        return None

    # Extract extractor configuration if present
    extractor_cfg = config_copy.pop("extractor", None)
    if extractor_cfg:
        config_copy["extractor"] = RegexExtractor(**extractor_cfg)

    # Create appropriate monitor type
    if monitor_type == "FileMonitor":
        # Add directories for FileMonitor
        config_copy["offset_dir"] = PYGTAIL_DIR
        return FileMonitor(**config_copy)
    elif monitor_type == "DockerAPIMonitor":
        # Add directories for DockerAPIMonitor
        config_copy["offset_dir"] = DOCKER_DIR
        return DockerAPIMonitor(**config_copy)
    else:
        print(f"Unsupported monitor type: {monitor_type}")
        return None


def load_monitors_from_config(config_path):
    """Load monitor configurations from a JSON file."""
    try:
        with open(config_path, "r", encoding="utf-8", errors="replace") as f:
            configs = json.load(f)

        monitors = []
        for config in configs:
            monitor = create_monitor_from_config(config)
            if monitor:
                monitors.append(monitor)
                print(
                    f"Created monitor: {monitor.__class__.__name__} for {monitor.app_name}/{monitor.service_name}"
                )

        return monitors
    except FileNotFoundError:
        print(f"Configuration file not found: {config_path}")
        return []
    except json.JSONDecodeError:
        print(f"Invalid JSON in configuration file: {config_path}")
        return []
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return []


def main():
    """Main entry point for the application."""
    # Initialize logging
    setup_logging(os.environ.get("LOG_LEVEL", "INFO"))

    # Path to the configuration file from environment variable
    config_file = CONFIG_PATH

    # Load monitors from configuration
    print(f"Loading configuration from: {config_file}")
    monitors = load_monitors_from_config(config_file)
    if not monitors:
        print("No valid monitors configured.")
        return

    # Create and start monitor manager
    manager = MonitorManager()
    for monitor in monitors:
        manager.add_monitor(monitor)

    try:
        print(f"Starting log monitors with config: {config_file}")
        print(f"Data directory: {DATA_DIR}")
        print(f"Running as user: {os.getuid()}:{os.getgid()}")
        manager.start_all()

        # Main thread loops instead of just waiting indefinitely
        while True:
            time.sleep(0.5)  # Check for interrupts every half second

    except KeyboardInterrupt:
        print("Shutting down monitors...")
        manager.stop_all()
        manager.wait_all(timeout=5.0)  # Give threads 5 seconds to clean up
        print("Shutdown complete.")


if __name__ == "__main__":
    main()
