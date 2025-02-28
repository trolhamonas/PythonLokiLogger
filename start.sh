#!/bin/sh
set -e

# Get the config directory and data directory from environment variables
CONFIG_DIR=$(dirname "$CONFIG_PATH")
DATA_DIR=${DATA_DIR:-/config/data}
PYGTAIL_DIR="$DATA_DIR/pygtail"
DOCKER_DIR="$DATA_DIR/docker"

echo "Starting log monitor container"
echo "CONFIG_PATH: $CONFIG_PATH"
echo "DATA_DIR: $DATA_DIR"

# Check if we're running as root (UID 0)
if [ "$(id -u)" = "0" ]; then
    echo "Running as root, will create directories and ensure proper permissions"

    # Create all necessary directories
    mkdir -p "$CONFIG_DIR" "$PYGTAIL_DIR" "$DOCKER_DIR"

    # Check if config file exists
    if [ ! -f "$CONFIG_PATH" ]; then
        echo "ERROR: Configuration file not found at $CONFIG_PATH"
        echo "Please provide a valid configuration file before starting the container."
        exit 1
    fi

    # Set permissions for all directories
    chown -R "${PUID:-1000}:${PGID:-1000}" "$CONFIG_DIR"
    chmod -R 755 "$CONFIG_DIR"

    echo "Starting application as user ${PUID:-1000}:${PGID:-1000}"
    exec su-exec "${PUID:-1000}:${PGID:-1000}" python /app/main.py
else
    # We're already running as a non-root user
    echo "Running as non-root user $(id -u):$(id -g)"

    # Try to create directories (may fail if we don't have permission)
    mkdir -p "$CONFIG_DIR" "$PYGTAIL_DIR" "$DOCKER_DIR" || echo "Warning: Could not create some directories. Make sure they exist and are writable."

    # Check if config file exists
    if [ ! -f "$CONFIG_PATH" ]; then
        echo "ERROR: Configuration file not found at $CONFIG_PATH"
        echo "Please provide a valid configuration file before starting the container."
        exit 1
    fi

    # Run the application
    exec python /app/main.py
fi