# Makefile for switching Flask environment files and running the app or tests

.PHONY: run-prod run-test test clean sass-dev sass-prod sass-test

# Default target
Default:
	@echo "[Makefile] No target specified. Use 'make run' to start the Flask app in development mode."

run:
	@echo "[Makefile] Using .flaskenv for development..."
	cp .flaskenv.dev .flaskenv
	make sass-dev &
	flask run --debug

run-prod:
	@echo "[Makefile] Using .flaskenv for production..."
	cp .flaskenv.prod .flaskenv
	make sass-prod 
	flask run

run-test:
	@echo "[Makefile] Using .flaskenv.test for testing..."
	cp .flaskenv.test .flaskenv
	make sass-test &
	flask run

test:
	@echo "[Makefile] Using .flaskenv.test for pytest..."
	cp .flaskenv.test .flaskenv
	make sass-test &
	pytest -s

clean:
	@echo "[Makefile] Cleaning up .flaskenv..."
	rm -f .flaskenv

sass-dev sass-test:
	sass --watch app/static/scss:app/static/css --sourcemap=none

sass-prod:
	sass app/static/scss:app/static/css --style=compressed --no-source-map
