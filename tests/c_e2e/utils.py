# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.modules.wire.models import ArticlePost

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def create_stuff(db_session: Session) -> dict[str, User | ArticlePost]:
    """Creates a default user and an article for testing."""
    # Create or get the PRESS_MEDIA role
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    # Create or get user ID 0 for testing (used by authenticate_user hook as fallback)
    owner = db_session.query(User).filter_by(id=0).first()
    if not owner:
        owner = User(id=0, email="test@example.com")
        owner.photo = b""  # Empty bytes to avoid None errors
        owner.roles.append(role)
        db_session.add(owner)
        db_session.flush()

    article = ArticlePost(owner=owner)
    db_session.add(article)
    db_session.commit()

    return {
        "user": owner,
        "article": article,
    }


def login(client: FlaskClient) -> None:
    """Logs a user in via the test backdoor."""
    response = client.get("/backdoor/press_media")
    # The backdoor should redirect (302) after successful login
    assert response.status_code == 302, (
        f"Login failed with status {response.status_code}. "
        f"Expected 302 redirect after successful login."
    )
