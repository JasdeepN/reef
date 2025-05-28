# ReefDB Coral Management Web App

**Copyright (c) 2025 Jasdeep Nijjar  
All rights reserved.  
Commercial use, copying, or redistribution of this software or any substantial portion of it is strictly prohibited without the express written permission of the copyright holder. For commercial licensing, please contact jasdeepn4@gmail.com.**

---

## Overview

ReefDB (subject to change) is a web application for managing corals and aquarium data. Currently a work-in-progress; major changes to DB structure, API endpoints, features, and UI are possible between commits. Provides features for tracking coral taxonomy, tank assignments, health status, vendor information, and more. The app is built with Flask, SQLAlchemy, and Bootstrap, and includes Prometheus metrics for monitoring.

## Current Features

- Add, view, and manage coral records
- Dynamic taxonomy selection (type, genus, species, popular color morphs)
- Health, PAR, and placement tracking
- Prometheus metrics integration for monitoring
- Responsive Bootstrap UI
- Display and management of water parameter test results (Test Results page)
- Comprehensive searchable/filterable coral database (Database page)
- Export of test history in a format compatible with Grafana for advanced visualization and analysis
- Tracking for all common Reef parameters 
    - Salinity (SG)
    - Alkalinity (KH)
    - Phosphate (PO₄³⁻ ppm)
    - Phosphate (PO₄³⁻ ppb)
    - Nitrate (NO₃⁻ ppm)
    - Calcium (Ca²⁺ ppm)
    - Magnesium (Mg²⁺ ppm)
    - pH (tracked through probe every 15 seconds)

## Planned Upgrades

- User picture upload linked to specific corals
    - Used for timeline
- Direct doser control
- ReefPi Integration 
- Computer Vision/AI based basic identification
- Care requirements by species/genus 
- Compatability concerns (placement suggestion)
- Integrate Environmental Monitoring around tank (CO&#x2082; can affect KH)
- Scale app using gunicorn workers with nginx or some other loadbalancer (*if i decide to host this somewhere for users*)
    - register, login, accounts etc.
 Link test results with coral health
- ICP test result tracking
- Reminders for testing
- Alerts when dosing containers are empty
- Trend analysis + Recommended Dosing Changes to keep stability 


### Upgrade Notes
***Planned upgrades may change based on project needs and what I feel like is needed (and feel like working on). 
Features listed here are not guaranteed.***

## Setup

ReefDB now uses Docker containers for all environments to ensure consistency and easy deployment.

### Prerequisites

- Docker and Docker Compose
- Make (for using the Makefile commands)
- Git

### Quick Start

1. **Clone the repository**
    ```bash
    git clone https://github.com/JasdeepN/reefdb.git
    cd reefdb/web
    ```

2. **Start development environment**
    ```bash
    make start-dev
    ```
    This will:
    - Build the development Docker image
    - Start MySQL database on port 3306
    - Start Flask web container on port 5000 with auto-reload
    - Start Sass compilation in watch mode
    
    **Note**: On first startup, the container's entrypoint will automatically create database tables and seed initial data. No external SQL seed files are required.
    
3. **Access the app**  
   Open your browser and go to [http://localhost:5000](http://localhost:5000) for development

### Environment System

ReefDB uses a three-tier Docker environment system:

- **Development**: 
  - Database: MySQL (latest) on port 3306
  - Web: Flask dev server on port 5000 with auto-reload
  - File changes automatically reload the container
  - Traefik routing: `rdb-dev.server.lan` / `rdb-dev.lan`

- **Production**: 
  - Database: MySQL (latest) on port 3142  
  - Web: Gunicorn server on ports 5371 and 33812
  - Optimized for performance with health checks

- **Testing**: 
  - Database: Ephemeral MySQL container on port 3310
  - Web: Flask test server on port 5001

### Makefile Commands

```bash
# Environment Management
make start-dev      # Start development (DB:3306, Web:5000)
make start-prod     # Start production (DB:3142, Web:5371 & 33812)  
make start-test     # Start test (DB:3310, Web:5001)

# Stop Services
make stop-flask     # Stop all Flask web services (leave DBs running)
make stop-flask-dev # Stop development Flask container only
make stop-flask-prod # Stop production Flask container only
make stop-flask-test # Stop test Flask container only
make stop-all       # Stop everything (web + databases)

# Database Management
make start-db-dev   # Start development database container
make stop-db-dev    # Stop development database container
make start-db-prod  # Start production database container
make stop-db-prod   # Stop production database container

# Development Tools
make build-dev      # Build development Docker image
make status         # Show current environment status
make help           # Show all available commands
```

### Manual Setup (Alternative)

If you prefer not to use Docker:

1. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

2. **Configure environment variables**  
   Set your database credentials and other environment variables as needed.

3. **Initialize the database**
    ```bash
    flask db upgrade
    ```

4. **Run the application**
    ```bash
    flask run
    ```

## Testing

### Overview

The project includes comprehensive testing with both unit tests and end-to-end (E2E) tests:
- **Unit tests**: Fast API and route tests that don't require a running Flask server
- **E2E tests**: Full browser automation tests using Playwright that test the complete user workflow

### Container Management

The application uses Docker containers with MySQL (latest) for all environments:

- **Development containers**: Uses `reef-sql-dev` database and `reefdb-web-dev` web container
- **Production containers**: Uses `reef-sql-prod` database and `reefdb-web-prod` web container  
- **Test database**: Uses ephemeral `reef-sql-test` container on port 3310
- **CI tests**: Uses GitHub Actions services or `act` containers

### Quick Testing Commands

```bash
# Validate the entire container management setup
make validate

# Run all unit tests (fast, no Flask server required)
make test-unit

# Run E2E tests (requires running Flask server)
make test-e2e

# Start/stop ephemeral test database
make test-db-start
make test-db-stop
make test-db-restart

# Run CI tests locally with act (with automatic cleanup)
make act-test

# Clean up act containers manually
make act-clean
```

### Local Testing Setup

1. **Install test dependencies** (if not already done):
    ```bash
    pip install -r requirements.txt
    python -m playwright install --with-deps
    ```

2. **For E2E tests, start the test database and Flask server**:
    ```bash
    make start-test
    ```

3. **For unit tests only** (no Flask server needed):
    ```bash
    make test-unit
    ```

### CI Testing with act

To run the same tests that GitHub Actions runs locally:

```bash
# Install act if not already installed
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run CI tests (automatically cleans up containers)
make act-test
```

The `act` configuration is optimized to:
- Automatically remove containers after execution
- Use proper resource limits
- Clean up old containers before running new tests
- Keep only one MySQL test container running

### Container Cleanup

The testing system includes automatic container cleanup:

- **`.actrc`**: Configures `act` to automatically remove containers
- **`tests/scripts/cleanup_act_containers.sh`**: Removes old `act` containers and networks
- **`tests/scripts/run_act_tests.sh`**: Wrapper that runs cleanup before and after tests

If you see multiple database containers, run:
```bash
make act-clean
```

### Environment Variables

Test configuration is managed through `tests/.env.test`:

```bash
# Test database configuration
DB_PORT=3310
DB_NAME=reef_test
DB_USER=testuser
DB_PASS=testpassword
DB_HOST_ADDRESS=127.0.0.1
TEST_BASE_URL=http://127.0.0.1:5001

# Container configuration
CONTAINER=reef-sql-test
USE_MOUNTED_CONTAINER=false
```

### Flask Server Check

E2E tests automatically check if the Flask server is running before proceeding. If the server isn't accessible, you'll see:

```
[pytest] ❌ Flask server not accessible after 3 attempts: HTTPConnectionPool(host='172.0.10.1', port=5000): Read timed out. (read timeout=5)
[pytest] 💡 To start the Flask server, run: flask run --host=127.0.0.1 --port=5001
[pytest] 💡 Or use: make start-test
```

To start the server for testing:
```bash
make start-test  # Starts Flask on 127.0.0.1:5001 with test database
```

### Debugging Tests

If tests fail:

1. **Check container status**:
    ```bash
    make docker-status
    ```

2. **Check test database connection**:
    ```bash
    make test-db-status
    ```

3. **Run tests with verbose output**:
    ```bash
    pytest tests/ --ignore=tests/e2e/ -v  # Unit tests
    pytest tests/e2e/ -v                   # E2E tests
    ```

4. **Clean up all test containers**:
    ```bash
    make act-clean
    make test-db-stop
    ```

## License

This project is **not open source**.  
Commercial use, copying, or redistribution is strictly prohibited without written permission.  
For licensing inquiries, contact: jasdeepn4@gmail.com

---

**Maintainer:** Jasdeep Nijjar  
**Contact:** jasdeepn4@gmail.com