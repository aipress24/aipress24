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

## Quick e2e — skips the 169-profile slow smoke (default for local iteration).
test-e2e-local:
	pytest -v --browser firefox \
	--base-url=http://127.0.0.1:5000 \
	-m "not slow" e2e_playwright

## Full e2e including the 169-profile slow smoke (~10 minutes).
test-e2e-local-full:
	pytest -v --browser firefox \
	--base-url=http://127.0.0.1:5000 \
	e2e_playwright

## Quick e2e against prod — skips slow smoke and any mutating test.
test-e2e-prod:
	pytest -v --browser firefox \
	--base-url=$(PROD_URL) \
	-m "not slow" e2e_playwright

## Full e2e against prod — includes the 169-profile credential smoke.
test-e2e-prod-full:
	pytest -v --browser firefox \
	--base-url=$(PROD_URL) \
	e2e_playwright

## Per-module e2e shortcuts. Use `MOD=<name>` (default `wip`) to run a
## single module's tests against the local dev server. Faster than the
## full `test-e2e-local` (~3 min full → 30-60 s per module).
##
## Examples :
##   make test-e2e MOD=wip
##   make test-e2e MOD=bw
##   make test-e2e MOD=common
##
## Available modules : admin api biz bw common cross_modules events
##                     infra kyc notifications preferences public
##                     regressions security swork wip wire
MOD ?= wip
test-e2e:
	pytest -v --browser firefox \
	--base-url=http://127.0.0.1:5000 \
	-m "not slow" e2e_playwright/$(MOD)

## Parallel e2e — pytest-xdist with mail buffer per-worker isolation.
## 2 passes : (1) parallel-safe tests in N workers, (2) parallel_unsafe
## tests serial. The split is needed because some tests share seed-user
## state (password change, in-flight email change, BW activation on a
## specific guinea pig user). When multi-tenant fixtures (Sprint 7
## phase B) lands, parallel_unsafe should disappear.
##
## NWORKERS controls the parallel pass : `make test-e2e-parallel NWORKERS=4`.
NWORKERS ?= 4
test-e2e-parallel:
	pytest -v --browser firefox \
	--base-url=http://127.0.0.1:5000 \
	-n $(NWORKERS) --dist=loadfile \
	-m "not slow and not parallel_unsafe" e2e_playwright
	pytest -v --browser firefox \
	--base-url=http://127.0.0.1:5000 \
	-m "parallel_unsafe" e2e_playwright


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
	ty check src/app
	ty check tests
	pyrefly check src/app
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
