# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import uuid
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

    # IMPORTANT: Create user with ID 0 for testing mode
    # The app's authenticate_user hook (in hooks.py) looks for user ID 0 when app.testing=True
    test_user = db_session.query(User).filter_by(id=0).first()
    if not test_user:
        test_user = User(id=0, email="test@example.com")
        # Set minimal photo to avoid errors in template rendering
        test_user.photo = b""  # Empty bytes to avoid None errors
        test_user.roles.append(role)
        db_session.add(test_user)
        db_session.flush()

    # Create a second user for actual test usage
    unique_email = f"joe-{uuid.uuid4().hex[:8]}@example.com"
    owner = User(email=unique_email)
    owner.roles.append(role)
    db_session.add(owner)
    db_session.flush()  # Flush to get the auto-generated ID

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
