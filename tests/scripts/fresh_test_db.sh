#!/bin/bash

# Fresh Test Database Script
# Creates ephemeral test database container with live copy of dev data
# No persistent volumes - always starts clean with fresh dev data
#
# Usage:
#   fresh_test_db.sh [start|restart|stop|status]
#   
# Commands:
#   start (default) - Create fresh test database with live dev data
#   restart        - Stop existing and create fresh test database  
#   stop          - Stop and remove test database container
#   status        - Check test database container status

set -e

# Parse command line arguments
COMMAND=${1:-start}

case $COMMAND in
    start|restart)
        # Continue with main script logic
        ;;
    stop)
        echo "🛑 Stopping test database container..."
        if [ -f "$(dirname "$0")/../.env.test" ]; then
            source "$(dirname "$0")/../.env.test"
        fi
        TEST_CONTAINER_NAME=${CONTAINER:-reef-sql-test}
        docker stop $TEST_CONTAINER_NAME 2>/dev/null || echo "Container not running"
        docker rm $TEST_CONTAINER_NAME 2>/dev/null || echo "Container not found"
        echo "✅ Test database container stopped and removed"
        exit 0
        ;;
    status)
        echo "🔍 Checking test database status..."
        if [ -f "$(dirname "$0")/../.env.test" ]; then
            source "$(dirname "$0")/../.env.test"
        fi
        TEST_CONTAINER_NAME=${CONTAINER:-reef-sql-test}
        TEST_DB_PORT=${DB_PORT:-3310}
        
        if docker ps | grep -q $TEST_CONTAINER_NAME; then
            echo "✅ Test database container '$TEST_CONTAINER_NAME' is running"
            echo "   🔌 Port: $TEST_DB_PORT"
            echo "   🐳 Container ID: $(docker ps --filter name=$TEST_CONTAINER_NAME --format '{{.ID}}')"
            echo "   ⏰ Started: $(docker ps --filter name=$TEST_CONTAINER_NAME --format '{{.Status}}')"
        else
            echo "❌ Test database container '$TEST_CONTAINER_NAME' is not running"
        fi
        exit 0
        ;;
    *)
        echo "❌ Unknown command: $COMMAND"
        echo "Usage: $0 [start|restart|stop|status]"
        exit 1
        ;;
esac

# Source test environment variables
if [ -f "$(dirname "$0")/../.env.test" ]; then
    source "$(dirname "$0")/../.env.test"
fi

# Default values if not set in .env.test
TEST_CONTAINER_NAME=${CONTAINER:-reef-sql-test}
TEST_DB_NAME=${DB_NAME:-reef_test}
TEST_DB_USER=${DB_USER:-testuser}
TEST_DB_PASS=${DB_PASS:-testpassword}
TEST_ROOT_PASS=${DB_ROOT_PASS:-testrootpass}
TEST_DB_PORT=${DB_PORT:-3310}

# Development database connection (for copying data)
DEV_CONTAINER=${PROD_CONTAINER:-reef-sql-dev}
DEV_DB_NAME=${PROD_DB:-reef}

echo "🧪 Creating ephemeral test database with live dev data copy..."

if [ "$COMMAND" = "restart" ]; then
    echo "🔄 Restart command: Will recreate test database with fresh dev data"
fi

# Step 1: Stop and remove any existing test container
echo "🗑️  Cleaning up existing test containers..."
docker stop $TEST_CONTAINER_NAME 2>/dev/null || true
docker rm $TEST_CONTAINER_NAME 2>/dev/null || true

# Step 2: Verify dev container is running
echo "🔍 Checking development database availability..."
if ! docker ps | grep -q $DEV_CONTAINER; then
    echo "❌ Development database container '$DEV_CONTAINER' is not running!"
    echo "   Please start the development environment first: make start-dev"
    exit 1
fi

# Step 3: Get dev database password from environment
# Note: Due to persistent volumes, dev container may still use old password
DEV_ROOT_PASS="password"  # Current actual password in dev container
ENV_FILE_PATH="$(dirname "$0")/../../evs/.env.dev"
if [ -f "$ENV_FILE_PATH" ]; then
    ENV_PASS=$(grep "^MYSQL_ROOT_PASSWORD=" "$ENV_FILE_PATH" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
    echo "🔑 Environment file specifies password: $ENV_PASS"
    echo "⚠️  Note: Dev container uses persistent volume with old password: $DEV_ROOT_PASS"
fi

echo "📤 Creating live copy of development database..."

# Step 4: Export dev database to temporary file
DUMP_FILE="/tmp/dev_db_copy_$(date +%s).sql"
docker exec $DEV_CONTAINER mysqldump \
    -u root -p$DEV_ROOT_PASS \
    --single-transaction \
    --routines \
    --triggers \
    --add-drop-database \
    --databases $DEV_DB_NAME > "$DUMP_FILE"

echo "📊 Development data exported ($(du -h "$DUMP_FILE" | cut -f1))"

# Step 5: Create fresh ephemeral test container
echo "🚀 Starting ephemeral test database container..."
docker run -d \
    --name $TEST_CONTAINER_NAME \
    --rm \
    -p $TEST_DB_PORT:3306 \
    -e MYSQL_ROOT_PASSWORD=$TEST_ROOT_PASS \
    -e MYSQL_DATABASE=$TEST_DB_NAME \
    -e MYSQL_USER=$TEST_DB_USER \
    -e MYSQL_PASSWORD=$TEST_DB_PASS \
    -e MYSQL_CHARACTER_SET_SERVER=utf8mb4 \
    -e MYSQL_COLLATION_SERVER=utf8mb4_unicode_ci \
    mysql:latest

# Step 6: Wait for test database to be ready
echo "⏳ Waiting for test database to initialize..."
sleep 15
for i in {1..30}; do
    if docker exec $TEST_CONTAINER_NAME mysqladmin ping -h localhost -u root -p$TEST_ROOT_PASS --silent 2>/dev/null; then
        echo "✅ Test database container is ready!"
        break
    fi
    echo "   Waiting for database... ($i/30)"
    sleep 2
done

# Step 7: Import dev data into test database
echo "📥 Importing live dev data to test database..."

# Create the test database first
docker exec $TEST_CONTAINER_NAME mysql \
    -u root -p$TEST_ROOT_PASS \
    -e "CREATE DATABASE IF NOT EXISTS \`$TEST_DB_NAME\`;"

# Import the dump and rename database references
sed "s/CREATE DATABASE.*\`$DEV_DB_NAME\`/CREATE DATABASE IF NOT EXISTS \`$TEST_DB_NAME\`/g" "$DUMP_FILE" | \
sed "s/USE \`$DEV_DB_NAME\`/USE \`$TEST_DB_NAME\`/g" | \
docker exec -i $TEST_CONTAINER_NAME mysql -u root -p$TEST_ROOT_PASS

# Step 8: Verify test database setup
echo "🔍 Verifying test database with live data..."
TABLE_COUNT=$(docker exec $TEST_CONTAINER_NAME mysql \
    -u root -p$TEST_ROOT_PASS \
    -e "SELECT COUNT(*) as count FROM information_schema.tables WHERE table_schema='$TEST_DB_NAME';" \
    --skip-column-names 2>/dev/null | tail -1)

RECORD_COUNT=$(docker exec $TEST_CONTAINER_NAME mysql \
    -u root -p$TEST_ROOT_PASS \
    -e "SELECT COUNT(*) FROM tanks;" \
    --skip-column-names $TEST_DB_NAME 2>/dev/null | tail -1)

# Clean up dump file
rm -f "$DUMP_FILE"

echo ""
echo "✅ Ephemeral test database created successfully with live dev data!"
echo "   🐳 Container: $TEST_CONTAINER_NAME (ephemeral - no persistent volumes)"
echo "   🗄️  Database: $TEST_DB_NAME"
echo "   🔌 Port: $TEST_DB_PORT"
echo "   📊 Tables: $TABLE_COUNT"
echo "   🎯 Sample records (tanks): $RECORD_COUNT"
echo "   👤 Test user: $TEST_DB_USER"
echo "   🔑 Test passwords: Modified for testing environment"
echo ""
echo "🔗 Connection details for tests:"
echo "   Host: localhost"
echo "   Port: $TEST_DB_PORT"
echo "   Database: $TEST_DB_NAME"
echo "   User: $TEST_DB_USER"
echo "   Password: $TEST_DB_PASS"
echo ""
echo "📝 Manual connection:"
echo "   mysql -h localhost -P $TEST_DB_PORT -u $TEST_DB_USER -p$TEST_DB_PASS $TEST_DB_NAME"
echo ""
echo "⚡ Database contains live copy of current dev data - perfect for testing!"
