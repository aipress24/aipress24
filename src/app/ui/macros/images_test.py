# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest.mock import Mock

from flask_sqlalchemy.extension import SQLAlchemy

from app.models.auth import CommunityEnum, User
from app.models.orgs import Organisation
from app.ui.macros.images import org_logo, profile_image


def test_profile_image(db: SQLAlchemy) -> None:
    user = Mock(User)
    user.community_primary = CommunityEnum.PRESS_MEDIA
    user.community_secondary = CommunityEnum.COMMUNICANTS

    tag = profile_image(user, size=24)

    assert "blue" in tag
    assert "mock.profile_image_url" in tag


def test_org_logo(db: SQLAlchemy) -> None:
    org = Mock(Organisation)

    tag = org_logo(org, size=24)

    assert "mock.logo_url" in tag
