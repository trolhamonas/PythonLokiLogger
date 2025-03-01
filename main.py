"""Entry point for the log monitoring application."""

from typing import List, Optional, Dict
import os
import time
import json
import logging
import threading
from pythonlogloki.extractors import RegexExtractor
from pythonlogloki.monitors.base import Monitor
from pythonlogloki.monitors.file import FileMonitor
from pythonlogloki.monitors.docker import DockerAPIMonitor

# Configuration Constants
DEFAULT_CONFIG_PATH = "monitors.json"
DEFAULT_DATA_DIR = "data"
DEFAULT_LOG_LEVEL = "DEBUG"


class ConfigurationError(Exception):
    """Custom exception for configuration-related errors."""

    pass


class ConfigManager:
    """Manages application configuration and monitor creation."""

    def __init__(self):
        self.config_path = os.environ.get("CONFIG_PATH", DEFAULT_CONFIG_PATH)
        self.data_dir = os.environ.get("DATA_DIR", DEFAULT_DATA_DIR)
        self.pygtail_dir = os.path.join(self.data_dir, "pygtail")
        self.docker_dir = os.path.join(self.data_dir, "docker")
        self.logger = logging.getLogger("PythonLokiLogger")

    def setup_logging(self, log_level: str = DEFAULT_LOG_LEVEL) -> None:
        """Configure application logging with file and console handlers."""
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        log_file = os.path.join(self.data_dir, "log_monitor.log")
        handlers = [logging.StreamHandler()]

        try:
            handlers.append(logging.FileHandler(log_file))
        except Exception as e:
            self.logger.warning(f"Failed to setup file logging: {e}")

        logging.basicConfig(
            level=numeric_level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers,
        )

    def create_monitor(self, config: Dict) -> Optional[Monitor]:
        """Create a monitor instance from configuration."""
        config_copy = config.copy()
        monitor_type = config_copy.pop("type", None)

        if not monitor_type:
            raise ConfigurationError("Missing monitor type in configuration")

        if extractor_cfg := config_copy.pop("extractor", None):
            config_copy["extractor"] = RegexExtractor(**extractor_cfg)

        monitor_factories = {
            "FileMonitor": self._create_file_monitor,
            "DockerAPIMonitor": self._create_docker_monitor,
        }

        factory = monitor_factories.get(monitor_type)
        if not factory:
            raise ConfigurationError(f"Unsupported monitor type: {monitor_type}")

        return factory(config_copy)

    def _create_file_monitor(self, config: Dict) -> FileMonitor:
        """Create a FileMonitor instance."""
        config["offset_dir"] = self.pygtail_dir
        return FileMonitor(**config)

    def _create_docker_monitor(self, config: Dict) -> DockerAPIMonitor:
        """Create a DockerAPIMonitor instance."""
        config["offset_dir"] = self.docker_dir
        return DockerAPIMonitor(**config)

    def load_monitors(self) -> List[Monitor]:
        """Load and create monitors from configuration file."""
        try:
            with open(self.config_path, "r") as f:
                configs = json.load(f)

            monitors = []
            for config in configs:
                monitor = self.create_monitor(config)
                monitors.append(monitor)
                self.logger.debug(
                    f"Created monitor: {monitor.__class__.__name__} "
                    f"for {monitor.app_name}/{monitor.service_name} ({config['folder']})"
                )
            return monitors

        except FileNotFoundError:
            raise ConfigurationError(
                f"Configuration file not found: {self.config_path}"
            )
        except json.JSONDecodeError:
            raise ConfigurationError(
                f"Invalid JSON in configuration file: {self.config_path}"
            )
        except Exception as e:
            raise ConfigurationError(f"Error loading configuration: {e}")


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

    def wait_all(self, timeout: float = 1.0) -> None:
        """Wait for all monitor threads to complete with timeout."""
        end_time = time.time() + timeout
        for thread in self.threads:
            remaining = max(0, end_time - time.time())
            thread.join(timeout=remaining)


def main() -> None:
    """Main entry point for the application."""
    config_manager = ConfigManager()
    config_manager.setup_logging(os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL))
    logger = logging.getLogger("PythonLokiLogger")

    try:
        logger.info(f"Loading configuration from: {config_manager.config_path}")
        monitors = config_manager.load_monitors()

        if not monitors:
            logger.warning("No valid monitors configured.")
            return

        manager = MonitorManager()
        for monitor in monitors:
            manager.add_monitor(monitor)

        logger.info(f"Starting log monitors with config: {config_manager.config_path}")
        logger.info(f"Data directory: {config_manager.data_dir}")
        manager.start_all()

        while True:
            time.sleep(0.5)

    except KeyboardInterrupt:
        logger.info("Shutting down monitors...")
        manager.stop_all()
        manager.wait_all(timeout=1.0)
        logger.info("Shutdown complete.")
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


if __name__ == "__main__":
    main()
