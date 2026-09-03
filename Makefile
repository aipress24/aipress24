.PHONY: all
all: lint/ruff test lint

help:
	@adt help-make

#
# Tests
#
.PHONY: test test-with-sqla-warnings test-with-coverage test-with-typeguard test-cov-unit test-cov-all

## Run tests
test:
	@make test-sqlite test-postgres

test-sqlite:
	pytest tests

test-postgres:
	pytest tests --db-url="postgresql://localhost/aipress24_test"

## Run tests with coverage
test-with-coverage:
	pytest tests --cov=app --doctest-modules

test-cov: test-with-coverage

## Coverage report scoped to the a_unit tier. Views / routes are omitted
## (covered at b_integration + c_e2e tiers) — see .coveragerc-unit.
test-cov-unit:
	pytest tests/a_unit/ --cov=app --cov-config=.coveragerc-unit

## Full coverage report (a_unit + b_integration). Reuses .coveragerc-unit
## so views / routes are still omitted, but rolls in integration-tier
## hits so the per-module % reflects what is ACTUALLY tested across
## tiers. The unit-only report (`test-cov-unit`) over-counts misses on
## anything that's only reachable via real DB / Stripe / etc.
test-cov-all:
	pytest tests/a_unit/ tests/b_integration/ --cov=app --cov-config=.coveragerc-unit

test-with-typeguard:
	pytest tests --typeguard-packages=app

## Self-contained e2e: boots its own server on 8899, runs the suite,
## tears the server down, exits with pytest's status. Nothing else to
## start — a `make run` dev server can stay up on 5000.
##
## The server runs with FLASK_ACCEPT_ANY_PASSWORD so the suite can sign
## in against any database, including a restored production dump whose
## password hashes don't match the CSV fixtures.
##
## `mutates_db` and `slow` are excluded by default.
##
## Set E2E_BASE_URL to run against a server that is already up — a
## `make run` on 5000, or production — instead of starting one.
##
## Examples :
##   make test-e2e                       # whole suite, no DB writes
##   make test-e2e MOD=kyc               # one module
##   make test-e2e E2E_ALL=1             # include mutates_db + slow
##   make test-e2e E2E_PYTEST_ARGS=-q    # dots, not one line per test
##   make test-e2e E2E_BASE_URL=http://127.0.0.1:5000
##   make test-e2e E2E_BASE_URL=https://aipress24.com E2E_MARKERS='not slow'
##
## Available modules : admin api biz bw common cross_modules events
##                     infra kyc notifications preferences public
##                     regressions security swork wip wire
export MOD
export E2E_ALL
export E2E_BASE_URL
export E2E_BROWSER
export E2E_MARKERS
export E2E_PORT
export E2E_PYTEST_ARGS
export E2E_SERVER_LOG

test-e2e:
	uv run python e2e_playwright/run_e2e.py


#
# Lint
#
.PHONY: lint/ruff lint hadolint audit

check: lint

lint/ruff:
	ruff check


## Lint source code and check typing
lint:
	ruff check
	vulture --min-confidence 80 src
	ty check src tests
	pyrefly check src/app tests
	lint-imports
	# deptry src
	# mypy --show-error-codes src

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


## Run the production stack locally (granian + worker + scheduler)
run-prod:
	flask db upgrade
	honcho -f Procfile start web worker scheduler


## Run POC server
run-poc:
	flask --app poc.app --debug run --reload


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


## Regenerate the public-API client SDK from the OpenAPI spec
.PHONY: api-sdk
api-sdk:
	uv run python sdk/python/export_spec.py sdk/python/openapi.json
	uv run python sdk/python/generate.py sdk/python/openapi.json
	uv run ruff format sdk/python/aipress24_client/_generated.py


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
