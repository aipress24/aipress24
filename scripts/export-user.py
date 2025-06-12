#!/usr/bin/env python3
from __future__ import annotations

import yaml
from yaml import Dumper

from app.flask.extensions import db
from app.flask.main import create_app
from app.models.repositories import UserRepository


def export_user():
    repo = UserRepository(session=db.session)
    user = repo.get(1)
    data = vars(user)
    exported_data = {}
    for k, v in sorted(data.items()):
        if k.startswith("_"):
            continue
        try:
            size = len(v)
        except TypeError:
            size = 1
        print(f"{k}: {type(v)}, {size}")
        exported_data[k] = v

    yaml.dump(exported_data, open("tmp/user1.yaml", "w"), Dumper=Dumper)

    profile = user.profile
    data = vars(profile)
    exported_data = {}
    for k, v in sorted(data.items()):
        if k.startswith("_"):
            continue
        try:
            size = len(v)
        except TypeError:
            size = 1
        print(f"{k}: {type(v)}, {size}")
        exported_data[k] = v
    yaml.dump(exported_data, open("tmp/user1-profile.yaml", "w"), Dumper=Dumper)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        export_user()
