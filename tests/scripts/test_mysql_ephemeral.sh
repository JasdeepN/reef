#!/bin/bash
# Bring up an ephemeral MySQL test container for reefdb, using a copy of the prod DB
# Usage: ./test_mysql_ephemeral.sh [start|stop|status|restart]
# The container is named reef-sql-test and exposes port 3310

# Load .env.test from the tests directory (parent of this script)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TESTS_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$TESTS_DIR/.env.test"
if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

# Option to use a pre-mounted (persistent) test DB container
USE_MOUNTED_CONTAINER=${USE_MOUNTED_CONTAINER:-false}

case "$1" in
  start)
    # Always remove old container if it exists
    if docker ps -a --format '{{.Names}}' | grep -q "^$CONTAINER$"; then
      echo "Removing old MySQL test container: $CONTAINER"
      docker rm -f $CONTAINER
    fi
    if [ "$USE_MOUNTED_CONTAINER" = "true" ]; then
      if docker ps | grep -q $CONTAINER; then
        echo "Using already running mounted test DB container: $CONTAINER"
        exit 0
      else
        echo "No mounted test DB container found, starting a new one (will not auto-stop)."
        docker run -d \
          --name $CONTAINER \
          -e MYSQL_DATABASE=$DB_NAME \
          -e MYSQL_USER=$DB_USER \
          -e MYSQL_PASSWORD=$DB_PASS \
          -e MYSQL_ROOT_PASSWORD=$DB_ROOT_PASS \
          -p $DB_PORT:3306 \
          mysql:lts
        echo "Waiting for test MySQL to be ready..."
        sleep 15
        if [ ! -f "$DUMP_FILE" ]; then
          echo "Dumping prod DB from $PROD_CONTAINER to $DUMP_FILE..."
          docker exec $PROD_CONTAINER mysqldump -u root -ppassword $PROD_DB > "$DUMP_FILE"
        else
          echo "Using existing dump file: $DUMP_FILE"
        fi
        echo "Importing prod DB into test container..."
        cat "$DUMP_FILE" | docker exec -i $CONTAINER mysql -u root -p$DB_ROOT_PASS $DB_NAME
        echo "Applying user/privilege grants after prod DB import..."
        cat "$TESTS_DIR/seed_users.sql" | docker exec -i $CONTAINER mysql -u root -p$DB_ROOT_PASS $DB_NAME
        echo "DEBUG: MySQL users after grants:"
        docker exec $CONTAINER mysql -u root -p$DB_ROOT_PASS -e "SELECT user, host FROM mysql.user WHERE user='testuser';"
        echo "MySQL test container started on port $DB_PORT with prod DB copy and testuser grants."
        exit 0
      fi
    fi
    docker run -d --rm \
      --name $CONTAINER \
      -e MYSQL_DATABASE=$DB_NAME \
      -e MYSQL_USER=$DB_USER \
      -e MYSQL_PASSWORD=$DB_PASS \
      -e MYSQL_ROOT_PASSWORD=$DB_ROOT_PASS \
      -p $DB_PORT:3306 \
      mysql:lts
    echo "Waiting for test MySQL to be ready..."
    sleep 15
    if [ ! -f "$DUMP_FILE" ]; then
      echo "Dumping prod DB from $PROD_CONTAINER to $DUMP_FILE..."
      docker exec $PROD_CONTAINER mysqldump -u root -ppassword $PROD_DB > "$DUMP_FILE"
    else
      echo "Using existing dump file: $DUMP_FILE"
    fi
    echo "Importing prod DB into test container..."
    cat "$DUMP_FILE" | docker exec -i $CONTAINER mysql -u root -p$DB_ROOT_PASS $DB_NAME
    echo "Applying user/privilege grants after prod DB import..."
    cat "$TESTS_DIR/seed_users.sql" | docker exec -i $CONTAINER mysql -u root -p$DB_ROOT_PASS $DB_NAME
    echo "DEBUG: MySQL users after grants:"
    docker exec $CONTAINER mysql -u root -p$DB_ROOT_PASS -e "SELECT user, host FROM mysql.user WHERE user='testuser';"
    echo "MySQL test container started on port $DB_PORT with prod DB copy and testuser grants."
    ;;
  stop)
    if [ "$USE_MOUNTED_CONTAINER" = "true" ]; then
      echo "USE_MOUNTED_CONTAINER is true, not stopping the container."
      exit 0
    fi
    echo "Stopping ephemeral MySQL test container..."
    docker stop $CONTAINER
    ;;
  status)
    docker ps | grep $CONTAINER && echo "Container is running." || echo "Container is not running."
    ;;
  restart)
    if [ "$USE_MOUNTED_CONTAINER" = "true" ]; then
      echo "Restarting ephemeral MySQL test container with fresh prod DB copy (persistent mode, will not stop container)..."
      $0 start
      exit 0
    fi
    echo "Restarting ephemeral MySQL test container with fresh prod DB copy..."
    $0 stop
    $0 start
    ;;
  *)
    echo "Usage: $0 [start|stop|status|restart]"
    exit 1
    ;;
esac
