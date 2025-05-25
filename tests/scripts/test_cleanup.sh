#!/bin/bash
# Simple test of cleanup functionality

echo "Starting cleanup test..."

# Check for act containers
echo "Checking for act containers..."
ACT_CONTAINERS=$(docker ps -a --filter "name=act-" -q)
if [ ! -z "$ACT_CONTAINERS" ]; then
    echo "Found act containers: $ACT_CONTAINERS"
    docker rm -f $ACT_CONTAINERS
    echo "Removed act containers"
else
    echo "No act containers found"
fi

# Show current status
echo "Current MySQL containers:"
docker ps --filter "ancestor=mysql" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"

echo "Cleanup test complete!"
