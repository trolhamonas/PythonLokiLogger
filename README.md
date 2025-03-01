# PythonLokiLogger

PythonLokiLogger is a log monitoring tool that collects log entries from different sources and forwards them to Loki. It supports monitoring log files and Docker logs, providing centralized log aggregation and analysis.\
Why? Because grafana alloy was built different for me and this allows some flexibility for setting log level

## Features

- **Multiple Log Sources:** Monitor logs from files and Docker.
- **Configurable Monitoring:** Control polling frequency and log extraction using regular expressions.
- **Docker-Ready:** Easily deploy with Docker for containerized environments.
- **Simple Setup:** Get started quickly with a straightforward configuration.

## Getting Started

### Prerequisites

- **Docker** (if you plan on using the containerized version)
- **Python 3.11 or higher** (if running directly outside the container)

### Installation

#### Clone the Repository

```bash
git clone <repository-url>
cd PythonLokiLogger
```

#### Using Docker

1. **Build the Docker Image:**

   ```bash
   docker build -t pythonlokilogger .
   ```

2. **Prepare Your Configuration:**

   Create a configuration file (for example, `monitors.json`) to define your log monitors. An example configuration entry:

   ```json
   [
     {
       "type": "FileMonitor",
       "app_name": "Your App Name",
       "service_name": "Your Service",
       "folder": "/path/to/logs",
       "poll_interval": 5,
       "extractor": {
         "timestamp_regex": "^(\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}\\.\\d+)",
         "log_level_regex": "^\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}\\.\\d+\\|(\\w+)\\|"
       }
     }
   ]
   ```

3. **Run the Container:**

   Ensure your configuration file is accessible inside the container and set the required environment variables:

   ```bash
   docker run \
     -e CONFIG_PATH=/path/to/your/monitors.json \
     -e DATA_DIR=/path/to/data \
     -v /local/path/to/config:/path/to/your \
     -v /local/path/to/data:/path/to/data \
     pythonlokilogger
   ```

   The following environment variables are important:
    - **CONFIG_PATH:** Path to the monitor configuration file.
    - **DATA_DIR:** Directory for storing runtime data (logs, offsets, etc.).

#### Running Locally (Without Docker)

1. **Install Dependencies:**

   Install the required packages:

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Application:**

   ```bash
   python main.py
   ```

## Configuration

Adjust your monitor settings by editing the configuration file (e.g., `monitors.json`). Configure parameters such as the log source type, application and service names, directory paths, polling interval, and regular expressions for extracting timestamps and log levels.

## License

Specify your project’s license here.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request if you have suggestions, improvements, or bug fixes.

## Contact

If you have any questions or need support, feel free to reach out through GitHub issues.