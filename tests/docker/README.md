# Docker-based tests

Runs the test suite against PostgreSQL, with both the database and the tests in containers. Nothing to install but Docker.

```bash
make test-postgres-docker
```

The code is copied into the image (not bind-mounted), so it also works with a remote Docker context.

To run a subset of the tests:

```bash
docker compose -f tests/docker/compose.yaml run --rm --build tests-postgres pytest tests/b_integration
docker compose -f tests/docker/compose.yaml down
```

The database URL reaches pytest through `PYTEST_ADDOPTS`, so it applies to any `pytest` command run in the container.
