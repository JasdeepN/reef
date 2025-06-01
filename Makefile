# Makefile for ReefDB Flask application with Docker container support

.PHONY: build-dev build-prod build-test test clean sass-dev sass-prod sass-test build act-test act-clean docker-dev-start docker-dev-stop docker-prod-start docker-prod-stop docker-status test-db-start test-db-stop validate start-prod start-dev start-test stop-all kill-flask test-full test-simple stop-flask-dev stop-flask-prod stop-flask-test stop-flask start-db-dev stop-db-dev start-db-prod stop-db-prod restart restart-full dev-logs prod-logs test-logs

# === BASIC COMMANDS ===
run: 
	flask run 

build:
	python3 -m pip install --upgrade pip
	pip install -r requirements.txt
	python3 -m playwright install --with-deps

build-dev:
	@echo "[Makefile] Building development web image..."
	docker-compose -f docker-compose.dev.yml build reefdb-web-dev

clean:
	@echo "[Makefile] Cleaning up .env and CSS..."
	@rm -f .env || echo "No .env to remove"
	@rm -f app/static/css/*.css || echo "No CSS files to remove"
	@-pkill -f "flask run" 2>/dev/null || echo "No Flask processes to kill"

# === ENVIRONMENT SETUP ===
dev:
	@echo "[Makefile] Setting up development environment (port 5000)..."
	cp evs/.env.dev .env
	@echo "[Makefile] Development ready. Use 'make start-dev' to run."

prod:
	@echo "[Makefile] Setting up production environment (port 5371)..."
	cp evs/.env.prod .env
	make sass-prod
	@echo "[Makefile] Production ready. Use 'make start-prod' to run."

test:
	@echo "[Makefile] Setting up test environment (port 5001)..."
	cp evs/.env.test .env
	@echo "[Makefile] Test environment ready. Use 'make start-test' to run."

# === SERVER MANAGEMENT ===
start-prod: prod docker-prod-start
	@echo "[Makefile] Starting production environment with Docker containers..."
	@echo "[Makefile] Production database on port 3142"
	@echo "[Makefile] Production web container on ports 5371 and 33812"
	@echo "[Makefile] View logs with 'docker-compose -f docker-compose.prod.yml logs -f reefdb-web'"

start-dev: dev build-dev docker-dev-start
	@echo "[Makefile] Starting development environment with Docker containers..."
	@echo "[Makefile] Development database started on port 3306"
	@echo "[Makefile] Starting development web container (auto-reload on port 5000)..."
	docker-compose -f docker-compose.dev.yml up -d reefdb-web-dev
	@echo "[Makefile] Web container started. Follow logs with 'docker-compose -f docker-compose.dev.yml logs -f reefdb-web-dev'"
	make sass-dev &

start-test: test test-db-start
	@echo "[Makefile] Starting test Flask server on port 5001..."
	@echo "[Makefile] Test MySQL on port 3310, Flask on port 5001"
	make sass-test &
	FLASK_DEBUG=0 flask run --port=5001

stop-all:
	@echo "[Makefile] Stopping all Flask servers and databases..."
	@-pgrep -f "python.*flask run" | xargs -r kill || true
	@-pgrep -f "sass --watch" | xargs -r kill || true
	@echo "[Makefile] Stopping Docker containers..."
	@-docker-compose -f docker-compose.dev.yml down 2>/dev/null || echo "  Development containers already stopped"
	@-docker-compose -f docker-compose.prod.yml down 2>/dev/null || echo "  Production containers already stopped"
	@-docker stop reef-sql-test 2>/dev/null || echo "  Test database container already stopped"
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

# Stop only Flask web services per environment
.PHONY: stop-flask-dev stop-flask-prod stop-flask-test
stop-flask-dev:
	@echo "[Makefile] Stopping development Flask container..."
	@docker-compose -f docker-compose.dev.yml stop reefdb-web-dev

stop-flask-prod:
	@echo "[Makefile] Stopping production Flask container..."
	@docker-compose -f docker-compose.prod.yml stop reefdb-web

stop-flask-test:
	@echo "[Makefile] Stopping test Flask container..."
	@pkill -f "flask run --host=0.0.0.0 --port=5001" || true

# Alias to stop all Flask web containers without touching databases
.PHONY: stop-flask
stop-flask: stop-flask-dev stop-flask-prod stop-flask-test
	@echo "[Makefile] All Flask web services stopped (dev, prod, test)"

# Restart current web container with rebuild (keeps database running)
.PHONY: restart
restart:
	@if [ ! -f .env ]; then \
		echo "[Makefile] ERROR: No .env file found. Please run 'make dev', 'make prod', or 'make test' first."; \
		exit 1; \
	fi
	@current_env=$$(grep FLASK_ENV .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || echo 'unknown'); \
	echo "[Makefile] Detected current environment: $$current_env"; \
	case $$current_env in \
		development) \
			echo "[Makefile] Restarting development web container with rebuild (keeping DB running)..."; \
			docker-compose -f docker-compose.dev.yml stop reefdb-web-dev; \
			docker-compose -f docker-compose.dev.yml build --no-cache reefdb-web-dev; \
			docker-compose -f docker-compose.dev.yml up -d reefdb-web-dev; \
			echo "[Makefile] Development web container restarted on port 5000 (DB kept running)"; \
			;; \
		production) \
			echo "[Makefile] Restarting production web container with rebuild (keeping DB running)..."; \
			docker-compose -f docker-compose.prod.yml stop reefdb-web; \
			docker-compose -f docker-compose.prod.yml build --no-cache reefdb-web; \
			docker-compose -f docker-compose.prod.yml up -d reefdb-web; \
			echo "[Makefile] Production web container restarted on ports 5371 & 33812 (DB kept running)"; \
			;; \
		test) \
			echo "[Makefile] Restarting test environment..."; \
			pkill -f "flask run --host=0.0.0.0 --port=5001" || true; \
			docker stop reef-sql-test 2>/dev/null || true; \
			bash tests/scripts/test_mysql_ephemeral.sh start; \
			echo "[Makefile] Test environment restarted. Use 'make start-test' to run Flask."; \
			;; \
		*) \
			echo "[Makefile] ERROR: Unknown environment '$$current_env'. Expected: development, production, or test"; \
			exit 1; \
			;; \
	esac

# Restart entire environment including database (use with caution)
.PHONY: restart-full
restart-full:
	@if [ ! -f .env ]; then \
		echo "[Makefile] ERROR: No .env file found. Please run 'make dev', 'make prod', or 'make test' first."; \
		exit 1; \
	fi
	@current_env=$$(grep FLASK_ENV .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ' || echo 'unknown'); \
	echo "[Makefile] WARNING: Restarting ENTIRE environment including database: $$current_env"; \
	read -p "This will stop the database. Continue? (y/N): " confirm; \
	if [ "$$confirm" != "y" ] && [ "$$confirm" != "Y" ]; then \
		echo "[Makefile] Operation cancelled."; \
		exit 0; \
	fi; \
	case $$current_env in \
		development) \
			echo "[Makefile] Restarting entire development environment (web + database)..."; \
			docker-compose -f docker-compose.dev.yml down; \
			docker-compose -f docker-compose.dev.yml build --no-cache reefdb-web-dev; \
			docker-compose -f docker-compose.dev.yml up -d; \
			echo "[Makefile] Development environment fully restarted on port 5000"; \
			;; \
		production) \
			echo "[Makefile] Restarting entire production environment (web + database)..."; \
			docker-compose -f docker-compose.prod.yml down; \
			docker-compose -f docker-compose.prod.yml build --no-cache reefdb-web; \
			docker-compose -f docker-compose.prod.yml up -d; \
			echo "[Makefile] Production environment fully restarted on ports 5371 & 33812"; \
			;; \
		test) \
			echo "[Makefile] Restarting test environment..."; \
			pkill -f "flask run --host=0.0.0.0 --port=5001" || true; \
			docker stop reef-sql-test 2>/dev/null || true; \
			bash tests/scripts/test_mysql_ephemeral.sh start; \
			echo "[Makefile] Test environment restarted. Use 'make start-test' to run Flask."; \
			;; \
		*) \
			echo "[Makefile] ERROR: Unknown environment '$$current_env'. Expected: development, production, or test"; \
			exit 1; \
			;; \
	esac

# === SASS COMPILATION ===
sass-dev sass-test:
	sass --watch app/static/scss:app/static/css --sourcemap=none

sass-prod:
	sass app/static/scss:app/static/css --style=compressed --no-source-map

# === DATABASE MANAGEMENT ===
# Development database (MySQL 9.3 with existing data)
docker-dev-start:
	@echo "[Makefile] Starting development database container (port 3306)..."
	docker-compose -f docker-compose.dev.yml up -d
	@echo "[Makefile] Development database ready on port 3306"

docker-dev-stop:
	@echo "[Makefile] Stopping development database container..."
	docker-compose -f docker-compose.dev.yml down

docker-dev-logs:
	@echo "[Makefile] Showing development database logs..."
	docker-compose -f docker-compose.dev.yml logs -f

# Development web application logs
dev-logs:
	@echo "[Makefile] Showing development web application logs..."
	docker-compose -f docker-compose.dev.yml logs -f reefdb-web-dev

# Production containers (web app + MySQL)
docker-prod-start:
	@echo "[Makefile] Starting production containers (web + database)..."
	docker-compose -f docker-compose.prod.yml up -d
	@echo "[Makefile] Production containers ready - Web: ports 5371,33812; DB: port 3142"

docker-prod-stop:
	@echo "[Makefile] Stopping production containers..."
	docker-compose -f docker-compose.prod.yml down

docker-prod-logs:
	@echo "[Makefile] Showing production container logs..."
	docker-compose -f docker-compose.prod.yml logs -f

# Production web application logs
prod-logs:
	@echo "[Makefile] Showing production web application logs..."
	docker-compose -f docker-compose.prod.yml logs -f reefdb-web

docker-prod-build:
	@echo "[Makefile] Building production containers..."
	docker-compose -f docker-compose.prod.yml build

# Production deployment management
docker-prod-deploy: docker-prod-build docker-prod-start
	@echo "[Makefile] Deploying production environment..."
	@echo "[Makefile] Waiting for containers to start..."
	sleep 10
	@echo "[Makefile] Checking production health..."
	curl -s http://localhost:5371/health || echo "Health check failed - check logs"

# Docker container status
docker-status:
	@echo "[Makefile] Docker Container Status:"
	@echo "  Development Database:"
	@docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}" | grep reef-sql-dev || echo "    Not running"
	@echo "  Production Containers:"
	@docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}" | grep reef | grep prod || echo "    Not running"
	@echo "  Test Database:"
	@docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}" | grep reef-sql-test || echo "    Not running"

# Fresh test database with live dev data
test-db-start:
	@echo "[Makefile] Starting fresh test database with live dev data on port 3310..."
	bash tests/scripts/fresh_test_db.sh start

# Test database logs
test-logs:
	@echo "[Makefile] Showing test database logs..."
	docker logs -f reef-sql-test 2>/dev/null || echo "[Makefile] Test database container not running. Start with 'make test-db-start'"

test-db-stop:
	@echo "[Makefile] Stopping ephemeral test database..."
	bash tests/scripts/fresh_test_db.sh stop

test-db-status:
	@echo "[Makefile] Checking test database status..."
	bash tests/scripts/fresh_test_db.sh status

test-db-restart:
	@echo "[Makefile] Restarting test database with fresh dev data..."
	bash tests/scripts/fresh_test_db.sh restart

# Alias commands for starting/stopping database containers
.PHONY: start-db-dev stop-db-dev start-db-prod stop-db-prod
start-db-dev: docker-dev-start
	@echo "[Makefile] Alias: Started development DB container"
stop-db-dev: docker-dev-stop
	@echo "[Makefile] Alias: Stopped development DB container"
start-db-prod: docker-prod-start
	@echo "[Makefile] Alias: Started production DB container"
stop-db-prod: docker-prod-stop
	@echo "[Makefile] Alias: Stopped production DB container"

# === TESTING ===
test-unit:
	@echo "[Makefile] Running unit tests only (no E2E)..."
	cp evs/.env.test .env
	PYTHONPATH=. pytest tests/unit/ -v

test-e2e: test start-test
	@echo "[Makefile] Running E2E tests (Flask server on port 5001)..."
	@echo "[Makefile] Waiting for Flask server to start..."
	sleep 3
	PYTHONPATH=. pytest tests/e2e/ -v

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
	@echo "  Current .env:"
	@if [ -f .env ]; then echo "    $(shell grep FLASK_ENV .env 2>/dev/null || echo 'Unknown')"; else echo "    No .env file"; fi
	@echo "  Flask processes:"
	@ps aux | grep "flask run" | grep -v grep || echo "    No Flask processes running"
	@echo "  Docker containers:"
	@docker ps --format "table {{.Names}}\t{{.Ports}}\t{{.Status}}" | grep reef || echo "    No reef containers running"
	@echo "  Database health status:"
	@echo "    Development DB (port 3306): $(shell docker inspect reef-sql-dev --format='{{.State.Health.Status}}' 2>/dev/null || echo 'Container not found')"
	@echo "    Production DB (port 3142): $(shell docker inspect reef-sql-prod --format='{{.State.Health.Status}}' 2>/dev/null || echo 'Container not found')"
	@echo "    Test DB (port 3310): $(shell docker inspect reef-sql-test --format='{{.State.Health.Status}}' 2>/dev/null || echo 'Container not found')"

help:
	@echo "ReefDB Development Makefile"
	@echo ""
	@echo "Environment Setup:"
	@echo "  dev          - Set up development environment (port 5000)"
	@echo "  test         - Set up test environment (port 5001)"
	@echo "  prod         - Set up production environment (port 5371 & 33812)"
	@echo ""
	@echo "Server Management:"
	@echo "  start-dev    - Start development (DB:3306, Web:5000)"
	@echo "  start-test   - Start test (DB:3310, Web:5001)"
	@echo "  start-prod   - Start production (DB:3142, Web:5371 & 33812)"
	@echo "  restart      - Restart current web container with rebuild (keeps DB running)"
	@echo "  restart-full - Restart entire environment including database (CAUTION)"
	@echo "  stop-all     - Stop all servers and databases"
	@echo "  kill-flask   - Force kill all Flask servers and clear ports"
	@echo "  stop-flask-dev - Stop development Flask container only (leave DB)"
	@echo "  stop-flask-prod - Stop production Flask container only (leave DB)"
	@echo "  stop-flask-test - Stop test Flask container only (leave DB)"
	@echo "  stop-flask   - Stop all Flask web services (dev, prod, test)"
	@echo "  status       - Show current environment status"
	@echo ""
	@echo "Database Management:"
	@echo "  test-db-start    - Start test MySQL container (port 3310)"
	@echo "  test-db-stop     - Stop test MySQL container"
	@echo "  test-db-restart  - Restart test MySQL container"
	@echo "  test-db-status   - Check test database status"
	@echo "  start-db-dev - Start development database container"
	@echo "  stop-db-dev  - Stop development database container"
	@echo "  start-db-prod - Start production database container"
	@echo "  stop-db-prod  - Stop production database container"
	@echo ""
	@echo "Log Management:"
	@echo "  dev-logs     - Follow development web application logs"
	@echo "  prod-logs    - Follow production web application logs"
	@echo "  test-logs    - Follow test database logs"
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
