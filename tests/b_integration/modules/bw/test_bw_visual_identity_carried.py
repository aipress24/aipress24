# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""A new Business Wall inherits the organisation's logo and banner.

Re-subscribing creates a new row, and the page reads the *active* one.
Renewing therefore emptied an organisation's page of its identity with
no warning: the files were never deleted, they stayed attached to the
superseded row. Reported for Agence TCA, whose three walls held the
logo on the July one while the September one served a blank pixel.
"""

from __future__ import annotations

import uuid

import pytest

from app.lib.file_object_utils import create_file_object
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models.business_wall import BusinessWall

BW_TYPE = "news_agency"


def _wall(db_session, org_id, owner_id, **kwargs) -> BusinessWall:
    wall = BusinessWall(
        bw_type=BW_TYPE,
        status=kwargs.pop("status", "draft"),
        is_free=True,
        owner_id=owner_id,
        payer_id=owner_id,
        organisation_id=org_id,
        **kwargs,
    )
    db_session.add(wall)
    db_session.flush()
    return wall


@pytest.fixture
def logo():
    # Not `.save()`: the carry-over reads and writes the stored
    # metadata, and never the bytes, so the test needs no storage.
    return create_file_object(
        content=uuid.uuid4().bytes * 8,
        original_filename="logo.jpg",
        content_type="image/jpeg",
    )


def test_a_second_wall_inherits_the_first_one_s_logo(
    db_session, test_org, test_user_owner, logo
):
    first = _wall(db_session, test_org.id, test_user_owner.id)
    first.logo_image = logo
    first.logo_image_copyright = "© Agence TCA"
    db_session.flush()

    second = _wall(db_session, test_org.id, test_user_owner.id)

    assert second.logo_image is not None
    assert second.logo_image.path == first.logo_image.path
    assert second.logo_image_copyright == "© Agence TCA"


def test_an_upload_made_during_sign_up_wins(
    db_session, test_org, test_user_owner, logo
):
    """Inheriting must never overwrite what the new wall already has."""
    first = _wall(db_session, test_org.id, test_user_owner.id)
    first.logo_image = logo
    db_session.flush()
    own = create_file_object(
        content=b"own logo bytes",
        original_filename="own.jpg",
        content_type="image/jpeg",
    )

    second = _wall(db_session, test_org.id, test_user_owner.id, logo_image=own)

    assert second.logo_image.path == own.path


def test_a_first_wall_inherits_nothing(db_session, test_org, test_user_owner):
    only = _wall(db_session, test_org.id, test_user_owner.id)

    assert only.logo_image is None


def test_another_organisation_s_logo_is_not_borrowed(
    db_session, test_org, test_user_owner, logo
):
    """The lookup is scoped by organisation: a logo is an identity, and
    never a default for somebody else."""
    stranger = Organisation(name="Autre agence")
    db_session.add(stranger)
    db_session.flush()
    theirs = _wall(db_session, stranger.id, test_user_owner.id)
    theirs.logo_image = logo
    db_session.flush()

    mine = _wall(db_session, test_org.id, test_user_owner.id)

    assert mine.logo_image is None
