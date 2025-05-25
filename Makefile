# Makefile for switching Flask environment files and running the app or tests

.PHONY: build-dev build-prod build-test test clean sass-dev sass-prod sass-test build act-test act-clean test-db-start test-db-stop validate



run: 
	flask run 

run-dev:
	make sass-dev &
	make run --debug

dev:
	make build
	@echo "[Makefile] Using .flaskenv.dev for development..."
	cp evs/.flaskenv.dev .flaskenv

prod:
	make build
	@echo "[Makefile] Using .flaskenv.prod for production..."
	cp evs/.flaskenv.prod .flaskenv
	make sass-prod

test:
	make build
	@echo "[Makefile] Using .flaskenv.test for testing..."
	cp evs/.flaskenv.test .flaskenv
	make sass-test

test-run:
	@echo "[Makefile] Using .flaskenv.test for pytest..."
	cp evs/.flaskenv.test .flaskenv
	flask run --debug &		
	make sass-test &
	pytest -s

clean:
	@echo "[Makefile] Cleaning up .flaskenv..."
	rm -f .flaskenv
	rm -f app/static/css/*.css
	
sass-dev sass-test:
	sass --watch app/static/scss:app/static/css --sourcemap=none

sass-prod:
	sass app/static/scss:app/static/css --style=compressed --no-source-map

build:
	python3 -m pip install --upgrade pip
	pip install -r requirements.txt
	python3 -m playwright install --with-deps

# Container and testing targets
act-clean:
	@echo "[Makefile] Cleaning up act containers..."
	./tests/scripts/cleanup_act_containers.sh

act-test:
	@echo "[Makefile] Running CI tests with act (with cleanup)..."
	./tests/scripts/run_act_tests.sh

test-db-start:
	@echo "[Makefile] Starting ephemeral test database..."
	./tests/scripts/test_mysql_ephemeral.sh start

test-db-stop:
	@echo "[Makefile] Stopping ephemeral test database..."
	./tests/scripts/test_mysql_ephemeral.sh stop

test-db-restart:
	@echo "[Makefile] Restarting ephemeral test database..."
	./tests/scripts/test_mysql_ephemeral.sh restart

test-unit:
	@echo "[Makefile] Running unit tests only (no E2E)..."
	cp evs/.flaskenv.test .flaskenv
	pytest tests/ --ignore=tests/e2e/ -v

test-e2e:
	@echo "[Makefile] Running E2E tests (requires running Flask server)..."
	cp evs/.flaskenv.test .flaskenv
	pytest tests/e2e/ -v

test-server:
	@echo "[Makefile] Starting Flask server for E2E testing (172.0.10.1:5000)..."
	@echo "[Makefile] Press Ctrl+C to stop the server"
	cp evs/.flaskenv.test .flaskenv
	flask run --host=172.0.10.1 --port=5000

validate:
	@echo "[Makefile] Validating container management setup..."
	./tests/scripts/validate_container_setup.sh
