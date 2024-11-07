.PHONY: all
all: lint/ruff test lint

PROD_URL:=https://aipress24.herokuapp.com
# Same for now
DEMO_URL:=https://aipress24.herokuapp.com

help:
	@adt help-make

#
# Tests
#
.PHONY: test test-with-sqla-warnings test-with-coverage test-with-typeguard

## Run tests
test:
	@make test-sqlite test-postgres

test-sqlite:
	TEST_DATABASE_URI="sqlite:///:memory:" pytest

test-postgres:
	pytest

test-with-sqla-warnings:
	SQLALCHEMY_WARN_20=1 pytest -W always::DeprecationWarning

## Run tests with coverage
test-with-coverage:
	pytest --cov=app --doctest-modules

test-with-typeguard:
	pytest --typeguard-packages=app


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
	adt check
	ruff check
	lint-imports
	deptry src
	vulture --min-confidence 80 src
	mypy --show-error-codes tests

	# TODO later
	# make hadolint
	# mypy --show-error-codes --check-untyped-defs tests src
	# pyright tests
	# mypy --show-error-codes src
	# mypy --check-untyped-defs --show-error-codes src
	# python -m pyanalyze --config-file pyproject.toml src

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
	poetry install
	flask vite install

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
	rm -rf vite/dist
	rm -rf vite/node_modules

## Format source code
format:
	# black --target-version py311 src tests scripts migrations docker e2e_playwright *.py
	ruff format src tests scripts migrations docker e2e_playwright *.py
	isort src tests scripts migrations docker e2e_playwright *.py

## Cleanup code (using autoflake)
cleanup-code:
	autoflake -i -r --remove-all-unused-imports --remove-unused-variables --ignore-init-module-imports src

#
#  Build and deploy
#
.PHONY: build
build:
	flask vite build

.PHONY: bootstrap
bootstrap:
	flask bootstrap

.PHONY: ontologies
ontologies:
		flask ontologies import

.PHONY: fake
## Generate fake data
fake:
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
.PHONY: update-deps

## Update dependencies
update-deps:
	poetry update
	poetry export -f requirements.txt > requirements.txt
	poetry show -o

poetry.lock: pyproject.toml
	poetry update
	poetry export -f requirements.txt > requirements.txt


#
# Heroku & Clever
#

## Deploy to Heroku
deploy-heroku:
	poetry export -f requirements.txt > requirements.txt
	git diff --quiet
	flask vite build
	-git commit vite/dist -n -m "rebuild vite assets"
	adt bump-version daily
	git push heroku main

## Deploy to Heroku (uncluding the database)
deploy-heroku-full:
	make deploy-heroku
	make deploy-heroku-db

## Deploy DB to Heroku
deploy-heroku-db:
	echo "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" \
		| heroku pg:psql postgresql-dimensional-84632 --app aipress24
	# echo "GRANT ALL ON SCHEMA public TO postgres; GRANT ALL ON SCHEMA public TO public;" \
	#	| heroku pg:psql postgresql-dimensional-84632 --app aipress24
	pg_dump aipress24 > tmp/db.sql
	heroku pg:psql postgresql-dimensional-84632 --app aipress24 < tmp/db.sql
	rm -f tmp/db.sql


## Deploy top HOP3
deploy-hop3:
	git push hop3 main
