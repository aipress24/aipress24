#!/usr/bin/env python3

# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import sys

from rich import print

from app.flask.cli.bootstrap_user import import_user
from app.flask.main import create_app

DEFAULT_SOURCE = "tmp/user.yaml"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        source = sys.argv[1]
    else:
        source = DEFAULT_SOURCE
    app = create_app()
    with app.app_context():
        user = import_user(source)
        print(f"Imported user: {user}, roles: {user.roles}")
