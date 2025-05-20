# Makefile for switching Flask environment files and running the app or tests

.PHONY: build-dev build-prod build-test test clean sass-dev sass-prod sass-test build



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
