.PHONY: all
all: lint/ruff test lint

help:
	@adt help-make

#
# Tests
#
.PHONY: test test-with-sqla-warnings test-with-coverage test-with-typeguard

## Run tests
test:
	# @make test-sqlite test-postgres
	@make test-sqlite

test-sqlite:
	pytest tests

test-postgres:
	pytest tests --db-url="postgresql://localhost/aipress24_test"

## Run tests with coverage
test-with-coverage:
	pytest tests --cov=app --doctest-modules

test-with-typeguard:
	pytest tests --typeguard-packages=app


test-e2e-local:
	pytest -v --browser firefox \
	--base-url=http://127.0.0.1:5000 \
	--headed e2e_playwright


test-e2e-prod:
	pytest -v --browser firefox \
	--base-url=$(PROD_URL) \
	--headed e2e_playwright


#
# Lint
#
.PHONY: lint/ruff lint hadolint audit

##
lint/ruff:
	ruff check

## Lint source code and check typing
lint:
	ruff check
	# FIXME...
	# lint-imports
	deptry src
	vulture --min-confidence 80 src
	# Typecheck tests - mostly useless
	mypy --show-error-codes tests
	pyright tests
	# Typecheck src - much more useful but not ready yet
	# mypy --show-error-codes src
	# pyright src

	# TODO later
	# make hadolint
	# mypy --check-untyped-defs --show-error-codes src

## Run security audit
audit:
	pip-audit
	safety check


#
# Rest
#
.PHONY: develop run run-gunicorn clean tidy format cleanup-code

## Setup the development environment
develop:
	uv sync
	uv run flask vite install

## Run (dev) server
run:
	# python scripts/generate-forms3.py
	honcho -f Procfile-dev start

## Run server under gunicorn
run-gunicorn:
	gunicorn -b 127.0.0.1:5000 -w1 'app.flask.main:create_app()'

## Cleanup repository
clean:
	adt clean
	rm -rf .mypy_cache .pytest_cache .ruff_cache .import_linter_cache .hypothesis
	rm -f log/*
	rm -f geckodriver.log
	rm -rf .grimp_cache
	find . -name __pycache__ -print0 | xargs -0 rm -rf
	rm -rf .tox .nox

## Cleanup harder
tidy: clean
	rm -rf .venv
	rm -rf vite/dist
	rm -rf vite/node_modules

## Format source code
format:
	ruff format
	ruff check --fix
	markdown-toc -i README.md

## Safe fixes
fix:
	ruff check --fix

## Unsafe fixes
fix-hard:
	ruff check --fix --unsafe-fixes


#
#  Build and deploy
#
.PHONY: build
build:
	flask vite build

.PHONY: bootstrap
bootstrap:
	flask db2 drop
	flask db2 create
	flask bootstrap
	flask bootstrap-users

.PHONY: ontologies
ontologies:
	flask ontologies import

.PHONY: fake
## Generate fake data
fake:
	flask fetch-bootstrap-data
	flask fake --clean
	flask job bano

.PHONY: reset-db
## Delete and recreate database
reset-db:
	dropdb aipress24
	createdb aipress24

.PHONY: nlp
## Run NLP jobs
nlp:
	python src/app/jobs/nlp.py

#
# Doc
#
.PHONY: doc

## Generate documentation
doc:
	sqla2uml -p -m app > doc/src/dev/diagrams/db/model-detailed.puml
	sqla2uml -m app > doc/src/dev/diagrams/db/model-simple.puml
	plantuml doc/src/dev/diagrams/db/*.puml
	cd doc && make build


#
# Dependencies
#

## Update dependencies
update-deps:
	uv sync -U
	pre-commit autoupdate
	uv pip list --outdated

.PHONY: update-deps

#
# Deploy
#

## Deploy top HOP3
deploy-hop3:
	git push hop3 main

.PHONY: deploy-hop3
