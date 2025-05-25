# Makefile for ReefDB Flask application with dual environment support

.PHONY: build-dev build-prod build-test test clean sass-dev sass-prod sass-test build act-test act-clean test-db-start test-db-stop validate start-prod start-dev start-test stop-all kill-flask test-full test-simple

# === BASIC COMMANDS ===
run: 
	flask run 

build:
	python3 -m pip install --upgrade pip
	pip install -r requirements.txt
	python3 -m playwright install --with-deps

clean:
	@echo "[Makefile] Cleaning up .flaskenv and CSS..."
	rm -f .flaskenv
	rm -f app/static/css/*.css
	pkill -f "flask run" || true

# === ENVIRONMENT SETUP ===
dev:
	@echo "[Makefile] Setting up development environment (port 5000)..."
	cp evs/.flaskenv.dev .flaskenv
	@echo "[Makefile] Development ready. Use 'make start-dev' to run."

prod:
	@echo "[Makefile] Setting up production environment (port 5000)..."
	cp evs/.flaskenv.prod .flaskenv
	make sass-prod
	@echo "[Makefile] Production ready. Use 'make start-prod' to run."

test:
	@echo "[Makefile] Setting up test environment (port 5001)..."
	cp evs/.flaskenv.test .flaskenv
	@echo "[Makefile] Test environment ready. Use 'make start-test' to run."

# === SERVER MANAGEMENT ===
start-prod: prod
	@echo "[Makefile] Starting production Flask server on port 5000..."
	flask run

start-dev: dev
	@echo "[Makefile] Starting development Flask server on port 5000..."
	make sass-dev &
	flask run --debug

start-test: test test-db-start
	@echo "[Makefile] Starting test Flask server on port 5001..."
	@echo "[Makefile] Test MySQL on port 3310, Flask on port 5001"
	make sass-test &
	flask run

stop-all:
	@echo "[Makefile] Stopping all Flask servers and test database..."
	@pgrep -f "python.*flask run" | xargs -r kill || true
	@pgrep -f "sass --watch" | xargs -r kill || true
	@docker stop reef-sql-test 2>/dev/null || echo "  Database container already stopped or not found"
	@echo "[Makefile] Cleanup complete!"

kill-flask:
	@echo "[Makefile] Killing all Flask servers and clearing ports..."
	@echo "  Stopping Flask processes..."
	pkill -f "flask run" || true
	pkill -f "python.*flask" || true
	pkill -f "python.*index.py" || true
	@echo "  Stopping Sass processes..."
	pkill -f "sass --watch" || true
	@echo "  Checking for processes using ports 5000-5001..."
	@for port in 5000 5001; do \
		pid=$$(lsof -ti:$$port 2>/dev/null || true); \
		if [ -n "$$pid" ]; then \
			echo "    Killing process $$pid using port $$port"; \
			kill -9 $$pid 2>/dev/null || true; \
		fi; \
	done
	@echo "  Flask cleanup complete!"
# === SASS COMPILATION ===
sass-dev sass-test:
	sass --watch app/static/scss:app/static/css --sourcemap=none

sass-prod:
	sass app/static/scss:app/static/css --style=compressed --no-source-map

# === DATABASE MANAGEMENT ===
test-db-start:
	@echo "[Makefile] Starting ephemeral test database on port 3310..."
	bash tests/scripts/test_mysql_ephemeral.sh start

test-db-stop:
	@echo "[Makefile] Stopping ephemeral test database..."
	bash tests/scripts/test_mysql_ephemeral.sh stop

test-db-status:
	@echo "[Makefile] Checking test database status..."
	bash tests/scripts/test_mysql_ephemeral.sh status

test-db-restart: test-db-stop test-db-start

# === TESTING ===
test-unit:
	@echo "[Makefile] Running unit tests only (no E2E)..."
	cp evs/.flaskenv.test .flaskenv
	pytest tests/ --ignore=tests/e2e/ -v

test-e2e: test start-test
	@echo "[Makefile] Running E2E tests (Flask server on port 5001)..."
	@echo "[Makefile] Waiting for Flask server to start..."
	sleep 3
	pytest tests/e2e/ -v

test-full: test-db-restart test-unit test-e2e
	@echo "[Makefile] Running complete test suite..."

# === TESTING TARGETS ===
test-simple:
	@echo "Simple test working!"

# === CI/ACT TESTING ===
act-clean:
	@echo "[Makefile] Cleaning up act containers..."
	./tests/scripts/cleanup_act_containers.sh

act-test:
	@echo "[Makefile] Running CI tests with act (with cleanup)..."
	./tests/scripts/run_act_tests.sh

validate:
	@echo "[Makefile] Validating container management setup..."
	./tests/scripts/validate_container_setup.sh

# === DEVELOPMENT HELPERS ===
status:
	@echo "[Makefile] Environment Status:"
	@echo "  Current .flaskenv:"
	@if [ -f .flaskenv ]; then echo "    $(shell grep FLASK_ENV .flaskenv 2>/dev/null || echo 'Unknown')"; else echo "    No .flaskenv file"; fi
	@echo "  Flask processes:"
	@ps aux | grep "flask run" | grep -v grep || echo "    No Flask processes running"
	@echo "  MySQL containers:"
	@docker ps --format "table {{.Names}}\t{{.Ports}}" | grep mysql || echo "    No MySQL containers running"

help:
	@echo "ReefDB Development Makefile"
	@echo ""
	@echo "Environment Setup:"
	@echo "  dev          - Set up development environment (port 5000)"
	@echo "  test         - Set up test environment (port 5001)"
	@echo "  prod         - Set up production environment (port 5000)"
	@echo ""
	@echo "Server Management:"
	@echo "  start-dev    - Start development server with Sass watching"
	@echo "  start-test   - Start test server with test database"
	@echo "  start-prod   - Start production server"
	@echo "  stop-all     - Stop all servers and databases"
	@echo "  kill-flask   - Force kill all Flask servers and clear ports"
	@echo "  status       - Show current environment status"
	@echo ""
	@echo "Database Management:"
	@echo "  test-db-start    - Start test MySQL container (port 3310)"
	@echo "  test-db-stop     - Stop test MySQL container"
	@echo "  test-db-restart  - Restart test MySQL container"
	@echo "  test-db-status   - Check test database status"
	@echo ""
	@echo "Testing:"
	@echo "  test-unit    - Run unit tests only"
	@echo "  test-e2e     - Run E2E tests (starts test server)"
	@echo "  test-full    - Run complete test suite"
	@echo ""
	@echo "CI/Development:"
	@echo "  act-test     - Run GitHub Actions locally with act"
	@echo "  build        - Install dependencies"
	@echo "  clean        - Clean up files and stop processes"
	@echo "  validate     - Validate container setup"
