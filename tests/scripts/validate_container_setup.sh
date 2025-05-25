#!/bin/bash
# validate_container_setup.sh
# Comprehensive validation of the container management setup

set -e

# Get project root directory (two levels up from this script)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_ROOT"

echo "🔍 Validating ReefDB Container Management Setup"
echo "=============================================="

# Check if required files exist
echo "📁 Checking required files..."
REQUIRED_FILES=(
    ".actrc"
    "tests/scripts/cleanup_act_containers.sh" 
    "tests/scripts/run_act_tests.sh"
    "tests/.env.test"
    "tests/scripts/test_mysql_ephemeral.sh"
    ".github/workflows/ci.yml"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file exists"
    else
        echo "❌ $file missing"
    fi
done

# Check Makefile targets
echo ""
echo "📋 Checking Makefile targets..."
MAKEFILE_TARGETS=(
    "act-clean"
    "act-test" 
    "test-db-start"
    "test-db-stop"
    "test-unit"
    "test-e2e"
)

for target in "${MAKEFILE_TARGETS[@]}"; do
    if grep -q "^$target:" Makefile; then
        echo "✅ make $target available"
    else
        echo "❌ make $target missing"
    fi
done

# Check Docker containers
echo ""
echo "🐳 Current container status..."
echo "MySQL containers:"
docker ps --filter "ancestor=mysql" --format "table {{.Names}}\t{{.Image}}\t{{.Status}}" || echo "No MySQL containers found"

echo ""
echo "Act containers:" 
ACT_CONTAINERS=$(docker ps -a --filter "name=act-" -q)
if [ -z "$ACT_CONTAINERS" ]; then
    echo "✅ No act containers found (clean state)"
else
    echo "⚠️  Found act containers: $ACT_CONTAINERS"
fi

# Check act binary
echo ""
echo "🛠️  Checking act installation..."
if [ -f "bin/act" ]; then
    echo "✅ Local act binary found: $(./bin/act --version)"
elif command -v act >/dev/null 2>&1; then
    echo "✅ System act binary found: $(act --version)"
else
    echo "❌ No act binary found"
fi

# Test environment configuration
echo ""
echo "⚙️  Testing environment configuration..."
if [ -f "tests/.env.test" ]; then
    echo "Environment variables from tests/.env.test:"
    grep -E "^(DB_|TEST_|CONTAINER)" tests/.env.test | head -5
    echo "✅ Test environment configured"
else
    echo "❌ Test environment not configured"
fi

echo ""
echo "🎯 Validation complete!"
echo ""
echo "🚀 Quick start commands:"
echo "  make test-unit      # Run unit tests"
echo "  make act-clean      # Clean up act containers"  
echo "  make test-db-start  # Start test database"
echo "  make act-test       # Run CI tests with act"
echo ""
