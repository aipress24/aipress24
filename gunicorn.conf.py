# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""gunicorn WSGI server configuration."""

from multiprocessing import cpu_count

from hyperdx.opentelemetry import configure_opentelemetry


def post_fork(server, worker):
    configure_opentelemetry()


def max_workers():
    """Returns an amount of workers based on the number of CPUs in the system"""
    return cpu_count() + 1


# worker_class = 'eventlet'
# workers = max_workers()
workers = 1
threads = 1

preload_app = True
