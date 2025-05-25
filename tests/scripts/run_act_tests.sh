#!/bin/bash
# run_act_tests.sh
# Wrapper script that cleans up old containers before running act tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "🚀 Starting act CI tests..."

# Clean up any existing act containers first
if [ -f "$SCRIPT_DIR/cleanup_act_containers.sh" ]; then
    echo "🧹 Running cleanup first..."
    bash "$SCRIPT_DIR/cleanup_act_containers.sh"
fi

# Run act with the job specified (defaults to 'push' event)
EVENT_NAME=${1:-push}

echo "🏃 Running act event: $EVENT_NAME"

# Change to the project directory
cd "$PROJECT_ROOT"

# Run act with proper cleanup
ACT_PATH="$PROJECT_ROOT/bin/act"
if [ -f "$ACT_PATH" ]; then
    echo "🏃 Using local act binary: $ACT_PATH"
    "$ACT_PATH" "$EVENT_NAME"
elif command -v act >/dev/null 2>&1; then
    echo "🏃 Using system act binary"
    act "$EVENT_NAME"
else
    echo "❌ Error: 'act' command not found. Please install nektos/act first."
    echo "   You can install it with: curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash"
    echo "   Or place the act binary in $PROJECT_ROOT/bin/act"
    exit 1
fi

echo "✅ Act tests completed!"

# Optional: Clean up again after tests
echo "🧹 Post-test cleanup..."
bash "$SCRIPT_DIR/cleanup_act_containers.sh"
