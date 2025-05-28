# ReefDB Production Deployment Guide

## Quick Start

1. **Copy environment template:**
   ```bash
   cp .env.prod.template .env.prod
   ```

2. **Edit production environment:**
   ```bash
   nano .env.prod
   ```
   Fill in your actual database credentials and security keys.

3. **Deploy:**
   ```bash
   ./deploy-prod.sh
   ```

## Production Features

- **Port Configuration**: Uses port 5371 by default, falls back to 33812 if occupied
- **Health Checks**: Built-in health endpoint at `/health`
- **Security**: Runs as non-root user, secure session cookies
- **Logging**: Persistent logs in `/app/logs/`
- **Auto-restart**: Container restarts automatically unless stopped
- **Resource Optimization**: Preloaded workers, request limits, optimized Docker layers

## Production Deployment

**Database Initialization**: The production container's entrypoint will automatically create database tables and seed initial data if the database is empty. Remove manual SQL scripts from `setup/`.

## Manual Deployment

### Using Docker Compose (Recommended)

```bash
# Build and start
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Stop
docker-compose -f docker-compose.prod.yml down
```

### Using Docker directly

```bash
# Build image
docker build -t reefdb-prod .

# Run container
docker run -d \
  --name reefdb-prod \
  -p 5371:5371 \
  -p 33812:33812 \
  -e DB_USER=your_user \
  -e DB_PASS=your_password \
  -e DB_HOST=your_host \
  -e SECRET_KEY=your_secret_key \
  --restart unless-stopped \
  reefdb-prod
```

## Health Monitoring

The application includes a health check endpoint at `/health` that verifies:
- Application responsiveness
- Database connectivity
- Service status

Example response:
```json
{
  "status": "healthy",
  "database": "connected",
  "service": "reefdb"
}
```

## Environment Variables

### Required
- `DB_USER`: Database username
- `DB_PASS`: Database password
- `DB_HOST`: Database host
- `SECRET_KEY`: Flask secret key (32+ characters)

### Optional
- `DB_PORT`: Database port (default: 3306)
- `DB_NAME`: Database name (default: reef)
- `TIMEZONE`: Application timezone (default: US/Eastern)
- `GUNICORN_WORKERS`: Number of worker processes (default: 4)
- `GUNICORN_TIMEOUT`: Request timeout in seconds (default: 120)

## Security Considerations

1. **Change default secret key** in production
2. **Use HTTPS** with a reverse proxy (nginx, Apache)
3. **Secure database credentials** 
4. **Enable firewall** rules for necessary ports only
5. **Regular updates** of base images and dependencies

## Troubleshooting

### Port Issues
If both default ports are occupied:
```bash
# Check what's using the ports
netstat -tuln | grep -E "(5371|33812)"

# Find process ID
lsof -i :5371
```

### Container Logs
```bash
# Application logs
docker-compose -f docker-compose.prod.yml logs reefdb-web

# Access logs (inside container)
docker exec -it reefdb-web tail -f /app/logs/access.log

# Error logs (inside container)
docker exec -it reefdb-web tail -f /app/logs/error.log
```

### Health Check Failed
```bash
# Check health endpoint directly
curl http://localhost:5371/health

# Check container status
docker-compose -f docker-compose.prod.yml ps
```

## Backup and Maintenance

### Database Backup
```bash
# If using the included MySQL service
docker-compose -f docker-compose.prod.yml exec database mysqldump -u root -p reef > backup.sql
```

### Log Rotation
Logs are stored in `./logs/` and should be rotated regularly:
```bash
# Manual log rotation
docker-compose -f docker-compose.prod.yml exec reefdb-web rm /app/logs/*.log
docker-compose -f docker-compose.prod.yml restart reefdb-web
```

## Updates

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d
```
