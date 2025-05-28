#!/bin/bash
# Production deployment script for ReefDB

set -e

echo "=== ReefDB Production Deployment ==="
echo "Date: $(date)"
echo "User: $(whoami)"
echo "Directory: $(pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed and running
if ! command -v docker &> /dev/null; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! docker info &> /dev/null; then
    print_error "Docker is not running. Please start Docker first."
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    print_error "Docker Compose is not available. Please install Docker Compose."
    exit 1
fi

# Set compose command
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    COMPOSE_CMD="docker compose"
fi

### Check environment file
if [ ! -f "evs/.env.prod" ]; then
    print_warning "Production environment file (evs/.env.prod) not found."
    if [ -f "evs/.env.template" ]; then
        print_status "Copying template to evs/.env.prod"
        cp evs/.env.template evs/.env.prod
        print_warning "Please edit evs/.env.prod with your actual production values before continuing."
        print_warning "Run: nano evs/.env.prod"
        exit 1
    else
        print_error "No environment template found. Please create evs/.env.prod manually."
        exit 1
    fi
fi

# Create necessary directories
print_status "Creating necessary directories..."
mkdir -p logs flask_session static/temp

# Check for port conflicts
print_status "Checking for port conflicts..."
PORTS_TO_CHECK="3142 5371 33812"
CONFLICTED_PORTS=""

for port in $PORTS_TO_CHECK; do
    if netstat -tuln 2>/dev/null | grep -q ":$port "; then
        CONFLICTED_PORTS="$CONFLICTED_PORTS $port"
        case $port in
            3142) print_warning "Port 3142 (database) is already in use." ;;
            5371) print_warning "Port 5371 (web primary) is already in use. Will fallback to port 33812." ;;
            33812) print_warning "Port 33812 (web fallback) is already in use." ;;
        esac
    fi
done

# Check if database port is conflicted
if echo "$CONFLICTED_PORTS" | grep -q "3142"; then
    print_error "Port 3142 is required for the production database. Please free this port or stop the conflicting service."
    print_status "To find what's using port 3142: lsof -i :3142"
    exit 1
fi

# Check if both web ports are conflicted
if echo "$CONFLICTED_PORTS" | grep -q "5371" && echo "$CONFLICTED_PORTS" | grep -q "33812"; then
    print_error "Both web application ports (5371 and 33812) are in use. Please free at least one of them."
    exit 1
fi

# Build and deploy
print_status "Building ReefDB Docker image..."
$COMPOSE_CMD -f docker-compose.prod.yml build

print_status "Starting ReefDB in production mode..."
$COMPOSE_CMD -f docker-compose.prod.yml up -d

# Wait for health check
print_status "Waiting for services to become healthy..."
print_status "This may take up to 2 minutes for database initialization..."
sleep 15

# Check database health first
print_status "Checking database connectivity..."
max_db_wait=120  # 2 minutes for database
for i in $(seq 1 $max_db_wait); do
    if $COMPOSE_CMD -f docker-compose.prod.yml exec -T reefdb-database mysqladmin ping -h localhost -u root -p"${MYSQL_ROOT_PASSWORD:-prodroot2025!}" &>/dev/null; then
        print_status "Database is ready!"
        break
    fi
    if [ $i -eq $max_db_wait ]; then
        print_error "Database failed to start within $max_db_wait seconds"
        print_status "Database logs:"
        $COMPOSE_CMD -f docker-compose.prod.yml logs reefdb-database
        exit 1
    fi
    sleep 1
done

# Check web application health
print_status "Checking web application..."
sleep 5

# Check health endpoint
for port in 5371 33812; do
    if curl -f "http://localhost:$port/health" &>/dev/null; then
        print_status "ReefDB is running successfully!"
        print_status "Web Application: http://localhost:$port"
        print_status "Database: localhost:3142 (MySQL)"
        
        # Show container status
        echo
        print_status "Container status:"
        $COMPOSE_CMD -f docker-compose.prod.yml ps
        
        # Show logs
        echo
        print_status "Recent web application logs:"
        $COMPOSE_CMD -f docker-compose.prod.yml logs --tail=10 reefdb-web
        
        echo
        print_status "Recent database logs:"
        $COMPOSE_CMD -f docker-compose.prod.yml logs --tail=5 reefdb-database
        
        echo
        print_status "=== Deployment completed successfully! ==="
        print_status "Services:"
        print_status "  - Web App: http://localhost:$port"
        print_status "  - Database: localhost:3142 (root password: check .env.prod)"
        print_status "  - Logs: $COMPOSE_CMD -f docker-compose.prod.yml logs -f"
        print_status "  - Stop: $COMPOSE_CMD -f docker-compose.prod.yml down"
        print_status "  - Database backup: docker exec reef-sql-prod mysqldump -u root -p reef > backup.sql"
        exit 0
    fi
done

print_error "Health check failed. Check the logs for issues:"
$COMPOSE_CMD -f docker-compose.prod.yml logs reefdb-web
exit 1
