#!/usr/bin/env python3

import yaml
from devtools import debug

from app.flask.main import create_app

from app.flask.extensions import db
from app.models.repositories import UserRepository


def import_user():
    repo = UserRepository(session=db.session)

    data = yaml.load(open("tmp/user.yaml"), Loader=yaml.FullLoader)
    user = repo.add(data)
    debug(user)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        import_user()
