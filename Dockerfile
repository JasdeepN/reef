# Production Dockerfile for ReefDB Flask Application
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_ENV=production \
    FLASK_DEBUG=0

# Create non-root user
RUN groupadd -r reefdb && useradd -r -g reefdb reefdb

# Install system dependencies including MySQL development libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    default-libmysqlclient-dev \
    net-tools \
    netcat-traditional \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn[gevent]

# Copy application code and setup directories
COPY . /app/

# Copy entrypoint script
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Create necessary directories and copy production environment in one layer
RUN mkdir -p /app/flask_session /app/static/temp /app/logs && \
    cp evs/.env.prod .env && \
    chown -R reefdb:reefdb /app

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD curl -f http://localhost:5371/health || exit 1

# Switch to non-root user
USER reefdb

# Expose port
EXPOSE 5371

# Start the application
# Use entrypoint to initialize database and then start Gunicorn
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5371", "--workers", "4", "--worker-class", "gevent", "--timeout", "120", "--keep-alive", "2", "--max-requests", "1000", "--preload", "--log-level", "info", "--access-logfile", "/app/logs/access.log", "--error-logfile", "/app/logs/error.log", "wsgi:app"]
