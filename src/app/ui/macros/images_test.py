# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest.mock import Mock

import pytest
from flask_sqlalchemy.extension import SQLAlchemy

from app.enums import RoleEnum
from app.models.auth import User
from app.models.organisation import Organisation
from app.ui.macros.images import org_logo, profile_image


@pytest.mark.skip(reason="Mock(User) breaks the call user.first_community()")
def test_profile_image(db: SQLAlchemy) -> None:
    user = Mock(User)
    user.add_role(RoleEnum.PRESS_MEDIA)

    tag = profile_image(user, size=24)

    assert "red" in tag
    assert "mock.profile_image_url" in tag


@pytest.mark.skip(reason="Mock(User) breaks the property user.is_leader")
def test_org_logo(db: SQLAlchemy) -> None:
    org = Mock(Organisation)

    tag = org_logo(org, size=24)

    assert "mock.logo_url" in tag
