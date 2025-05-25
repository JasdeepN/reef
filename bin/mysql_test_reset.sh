#!/bin/bash
set -e

CONTAINER=reef-sql-test
DB_NAME=reef_test
DB_USER=testuser
DB_PASS=testpassword
DB_ROOT_PASS=testrootpass
PORT=3310

case "$1" in
  start)
    # Remove existing container if it exists
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
      echo "Removing old MySQL test container: $CONTAINER"
      docker rm -f $CONTAINER
    fi

    echo "Starting MySQL test container on port $PORT..."
    docker run -d \
      --name $CONTAINER \
      -e MYSQL_ROOT_PASSWORD=$DB_ROOT_PASS \
      -e MYSQL_DATABASE=$DB_NAME \
      -e MYSQL_USER=$DB_USER \
      -e MYSQL_PASSWORD=$DB_PASS \
      -p $PORT:3306 \
      mysql:8.0

    echo "Waiting for MySQL to be ready..."
    for i in {1..30}; do
      if docker exec $CONTAINER mysqladmin ping -h"127.0.0.1" --silent; then
        echo "MySQL is ready!"
        
        # Import seed data if it exists
        if [ -f "tests/seed.sql" ]; then
          echo "Importing seed data..."
          docker exec -i $CONTAINER mysql -u root -p$DB_ROOT_PASS $DB_NAME < tests/seed.sql
        fi
        
        exit 0
      fi
      echo "Waiting for MySQL... (attempt $i/30)"
      sleep 2
    done
    echo "MySQL failed to start properly"
    exit 1
    ;;
    
  stop)
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
      echo "Stopping MySQL test container: $CONTAINER"
      docker stop $CONTAINER
      docker rm $CONTAINER
    else
      echo "MySQL test container not running"
    fi
    ;;
    
  status)
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
      if docker exec $CONTAINER mysqladmin ping -h"127.0.0.1" --silent 2>/dev/null; then
        echo "MySQL test container is running and ready"
        exit 0
      else
        echo "MySQL test container is running but not ready"
        exit 1
      fi
    else
      echo "MySQL test container is not running"
      exit 1
    fi
    ;;
    
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 1
    ;;
esac
