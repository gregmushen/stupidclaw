FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create log and data directories
RUN mkdir -p /var/log/stupidclaw /var/data/stupidclaw

# Install cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Copy crontab
COPY crontab /etc/cron.d/stupidclaw
RUN chmod 0644 /etc/cron.d/stupidclaw && crontab /etc/cron.d/stupidclaw

# Entrypoint script forwards env vars to cron
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
