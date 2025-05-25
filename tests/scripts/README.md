# Test Scripts

This directory contains utility scripts for container management and testing in the ReefDB project.

```
tests/
├── scripts/
│   ├── README.md                    # This file
│   ├── cleanup_act_containers.sh    # Container cleanup
│   ├── run_act_tests.sh             # Act test runner
│   ├── validate_container_setup.sh  # Setup validation
│   ├── test_cleanup.sh              # Legacy test script
│   └── test_mysql_ephemeral.sh      # MySQL container management
├── .env.test                        # Test environment variables
├── seed.sql                         # Test database seed data
├── seed_users.sql                   # User/privilege setup
├── conftest.py                      # Pytest configuration
├── e2e/                            # End-to-end tests
└── unit/                           # Unit tests
```

## Scripts Overview

### `cleanup_act_containers.sh`
Comprehensive cleanup script that removes:
- Stopped act containers
- Running act containers  
- Orphaned MySQL containers from act
- Dangling networks created by act
- Shows current container status

**Usage:**
```bash
./tests/scripts/cleanup_act_containers.sh
# or
make act-clean
```

### `run_act_tests.sh`
Wrapper script for running GitHub Actions locally with `act`. Features:
- Cleans up containers before running tests
- Uses local or system `act` binary automatically
- Cleans up containers after tests complete
- Provides clear error messages and installation guidance

**Usage:**
```bash
./tests/scripts/run_act_tests.sh [job-name]
# or
make act-test
```

### `validate_container_setup.sh`
Validation script that checks all container management components:
- Verifies required files exist
- Checks Makefile targets are available
- Shows current container status
- Tests environment configuration
- Provides quick start commands

**Usage:**
```bash
./tests/scripts/validate_container_setup.sh
# or
make validate
```

### `test_cleanup.sh` (Legacy)
Simple test script for cleanup functionality. Used for debugging and testing individual cleanup components.

### `test_mysql_ephemeral.sh`
MySQL container management script for testing. Features:
- Start/stop/restart MySQL test containers
- Import production database dump
- Apply test user privileges and authentication
- Support for both ephemeral and persistent containers
- Automatic container cleanup and port management

**Usage:**
```bash
./tests/scripts/test_mysql_ephemeral.sh [start|stop|status|restart]
# or
make test-db-start  # start database
make test-db-stop   # stop database  
make test-db-restart # restart database
```

## File Structure

```
tests/
├── scripts/
│   ├── README.md                    # This file
│   ├── cleanup_act_containers.sh    # Container cleanup
│   ├── run_act_tests.sh             # Act test runner
│   ├── validate_container_setup.sh  # Setup validation
│   ├── test_cleanup.sh              # Legacy test script
│   └── test_mysql_ephemeral.sh      # MySQL container management
├── .env.test                        # Test environment variables
├── seed.sql                         # Test database seed data
├── seed_users.sql                   # User/privilege setup
├── conftest.py                      # Pytest configuration
├── e2e/                            # End-to-end tests
└── unit/                           # Unit tests
```

## Integration

All scripts are integrated with the main Makefile targets:

- `make validate` → `validate_container_setup.sh`
- `make act-clean` → `cleanup_act_containers.sh`
- `make act-test` → `run_act_tests.sh`
- `make test-db-start/stop/restart` → `test_mysql_ephemeral.sh`
- `make test-server` → Starts Flask server for E2E testing

## Dependencies

- **Docker**: For container management
- **act**: For local GitHub Actions testing (optional, can be installed automatically)
- **MySQL client**: For database testing and validation
- **Bash**: All scripts are written in Bash

## Environment Variables

Scripts respect the following environment variables from `tests/.env.test`:

- `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`: Database configuration
- `CONTAINER`: Test container name
- `TEST_BASE_URL`: Base URL for E2E tests

See the main README.md for complete setup and usage instructions.
