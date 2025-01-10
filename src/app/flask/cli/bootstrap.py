# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import command

from app.flask.bootstrap import bootstrap_db


#
# Other operational commands
#
@command("bootstrap")
@with_appcontext
def bootstrap_cmd() -> None:
    bootstrap_db(current_app)
