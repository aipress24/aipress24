#!/usr/bin/env python3

# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml
from arrow import Arrow
from yaml import Dumper

from app.flask.extensions import db
from app.flask.main import create_app
from app.models.repositories import UserRepository

TARGET_TMP = "tmp"
TARGET_FILE = "user.yaml"
USER_ID = 1


def stripped_content(obj: object) -> dict[str, Any]:
    return {k: v for k, v in vars(obj).items() if not k.startswith("_")}


def decimal_yaml_formater(dumper, dec: Decimal):
    return dumper.represent_scalar("!Decimal", str(dec))


def datetime_yaml_formater(dumper, dt: datetime | Arrow):
    return dumper.represent_scalar("!datetime", dt.isoformat())


def export(data: dict[str, Any]) -> None:
    Path(TARGET_TMP).mkdir(exist_ok=True)
    dest = Path(TARGET_TMP) / TARGET_FILE

    yaml.add_representer(Decimal, decimal_yaml_formater)
    yaml.add_representer(datetime, datetime_yaml_formater)
    yaml.add_representer(Arrow, datetime_yaml_formater)

    with dest.open("w") as f:
        yaml.dump(data, f, Dumper=Dumper, sort_keys=True)


def export_user():
    repo = UserRepository(session=db.session)
    user = repo.get(USER_ID)
    user_data = stripped_content(user)
    profile = user.profile
    profile_data = stripped_content(profile)
    roles = user.roles
    roles_data = [role.name for role in roles]

    user_data["_profile"] = profile_data
    user_data["_roles"] = roles_data

    export(user_data)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        export_user()
