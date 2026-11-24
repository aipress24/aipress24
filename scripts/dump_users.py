from devtools import debug
from sqlalchemy import inspect
from svcs.flask import container

from app.flask.main import create_app
from app.models.repositories import UserRepository, OrganisationRepository


def dump():
    app = create_app()
    with app.app_context():
        user_repo = container.get(UserRepository)
        org_repo = container.get(OrganisationRepository)

        users = user_repo.list()
        orgs = org_repo.list()

        user = users[0]
        debug(to_dict(user))


def to_dict(model):
    return {c.key: getattr(model, c.key)
            for c in inspect(model).mapper.column_attrs}


if __name__ == "__main__":
    dump()
