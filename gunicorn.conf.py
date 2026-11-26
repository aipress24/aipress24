# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""gunicorn WSGI server configuration, as production has it.

`hop3.toml` starts gunicorn from the repository root, which reads this file.
"""

from __future__ import annotations

import os

try:
    from hyperdx.opentelemetry import configure_opentelemetry
except ImportError:

    def configure_opentelemetry():
        pass


def post_fork(server, worker):
    configure_opentelemetry()


workers = int(os.environ.get("WEB_CONCURRENCY", "3"))
worker_class = "sync"
timeout = 30
graceful_timeout = 30

# Recycle the workers, so that no leak lasts.
max_requests = 1000
max_requests_jitter = 50

loglevel = "info"
accesslog = "-"
errorlog = "-"

# Each worker builds its own app: clients made before a fork (S3, database
# connections) cannot serve in the workers.
preload_app = False
