# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""gunicorn WSGI server configuration."""

import os
from multiprocessing import cpu_count

NODEJS_VERSION = "v18.16.0"
NODEJS_URL = (
    f"https://nodejs.org/dist/{NODEJS_VERSION}/node-{NODEJS_VERSION}-linux-x64.tar.xz"
)


# def on_starting(server):
#     """Executes code before the master process is initialized"""
#
#     if "DYNO" in os.environ:
#         run(f"curl {NODEJS_URL} > /tmp/nodejs.tar.xz")
#         run("tar --xz -xf /tmp/nodejs.tar.xz")
#         run(
#             f"ln -s /app/node-{NODEJS_VERSION}-linux-x64/bin/npm /app/.heroku/python/bin"
#         )
#         run(
#             f"ln -s /app/node-{NODEJS_VERSION}-linux-x64/bin/node /app/.heroku/python/bin"
#         )
#
#     run("flask vite install")
#     run("flask vite build")


def run(cmd):
    print(f"$ {cmd}")
    os.system(cmd)


def max_workers():
    """Returns an amount of workers based on the number of CPUs in the system"""
    return cpu_count() + 1


# worker_class = 'eventlet'
# workers = max_workers()
workers = 1
threads = 1

preload_app = True
