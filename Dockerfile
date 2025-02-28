FROM python:3.11-alpine

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install required packages
RUN apk add --no-cache su-exec && \
    pip install --no-cache-dir pygtail requests

# Create only the application directory (not the data directories)
RUN mkdir -p /app

# Copy application code
COPY pythonlogloki/ /app/pythonlogloki/
COPY main.py /app/

# Copy the start script
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Set working directory
WORKDIR /app

# The entrypoint script will handle directory creation and user switching
ENTRYPOINT ["/app/start.sh"]