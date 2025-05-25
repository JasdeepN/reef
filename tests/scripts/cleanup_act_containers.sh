#!/bin/bash
# cleanup_act_containers.sh
# Script to clean up old act containers and ensure only one MySQL test container runs

set -e  # Exit on error
echo "🧹 Cleaning up old act containers..."

# Remove all stopped act containers
STOPPED_ACT_CONTAINERS=$(docker ps -a --filter "name=act-" --filter "status=exited" -q)
if [ ! -z "$STOPPED_ACT_CONTAINERS" ]; then
    echo "Removing stopped act containers: $STOPPED_ACT_CONTAINERS"
    docker rm $STOPPED_ACT_CONTAINERS
else
    echo "No stopped act containers found."
fi

# Stop and remove any running act containers (except the one we want to keep)
RUNNING_ACT_CONTAINERS=$(docker ps --filter "name=act-" -q)
if [ ! -z "$RUNNING_ACT_CONTAINERS" ]; then
    echo "Stopping running act containers: $RUNNING_ACT_CONTAINERS"
    docker stop $RUNNING_ACT_CONTAINERS
    docker rm $RUNNING_ACT_CONTAINERS
fi

# Clean up any orphaned MySQL containers from act (keep main reef-sql)
ACT_MYSQL_CONTAINERS=$(docker ps -a --filter "name=act-" --filter "ancestor=mysql" -q)
if [ ! -z "$ACT_MYSQL_CONTAINERS" ]; then
    echo "Removing act MySQL containers: $ACT_MYSQL_CONTAINERS"
    docker rm -f $ACT_MYSQL_CONTAINERS
fi

# Clean up any dangling networks created by act (but preserve main 'act' network)
ACT_NETWORKS=$(docker network ls --filter "name=act-" -q)
if [ ! -z "$ACT_NETWORKS" ]; then
    echo "Removing dangling act networks: $ACT_NETWORKS"
    docker network rm $ACT_NETWORKS 2>/dev/null || true
fi

# Ensure the main 'act' network exists (required by act)
if ! docker network ls --format "{{.Name}}" | grep -q "^act$"; then
    echo "Creating required 'act' network..."
    docker network create act 2>/dev/null || echo "Failed to create 'act' network"
else
    echo "✅ Required 'act' network exists"
fi

echo "✅ Cleanup complete!"

# Show current container status
echo "📊 Current container status:"
docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" | grep -E "(NAME|mysql|act-|reef-sql)"
