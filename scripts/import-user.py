#!/usr/bin/env python3
import decimal

import yaml
from flask_security import hash_password
from sqlalchemy_utils.types.arrow import arrow

from app.flask.extensions import db
from app.flask.main import create_app
from app.models.auth import User
from app.models.repositories import UserRepository


def decimal_constructor(loader, node):
    value = loader.construct_scalar(node)
    return decimal.Decimal(value)


def arrow_constructor(loader, node):
    value = loader.construct_scalar(node)
    return arrow.get(value)


yaml.SafeLoader.add_constructor('!decimal', decimal_constructor)
yaml.SafeLoader.add_constructor('!arrow', arrow_constructor)


def import_user():
    data = yaml.load(open("tmp/user.yaml"), Loader=yaml.SafeLoader)
    password = data.pop("_password")
    user = User(**data)
    user.password = hash_password(password)

    repo = UserRepository(session=db.session)
    repo.add(user)
    db.session.commit()
    # debug(user)


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        import_user()
