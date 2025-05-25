#!/bin/bash
set -e

CONTAINER=reef-sql-test

# Remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "Removing old MySQL test container: $CONTAINER"
  docker rm -f $CONTAINER
fi

# Remove any anonymous or named volumes for the test DB (optional, if you use volumes)
# docker volume rm reefdb_mysql_data || true

echo "Ready to start a fresh MySQL test container."
