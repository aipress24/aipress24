# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for admin delete-bws view."""

from __future__ import annotations

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.views.delete_bws import _remove_all_bw
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus


class TestRemoveAllBw:
    """Test suite for the _remove_all_bw helper."""

    def test_remove_all_bw_deletes_records(self, db_session):
        """_remove_all_bw deletes all BusinessWalls and clears org fields."""
        org = Organisation(name="Test Org")
        user = User(email="test@example.com", organisation=org)
        db_session.add_all([org, user])
        db_session.flush()

        bw = BusinessWall(
            bw_type="media",
            status=BWStatus.ACTIVE.value,
            owner_id=int(user.id),
            payer_id=int(user.id),
            organisation_id=int(org.id),
            name="Test BW",
        )
        db_session.add(bw)
        org.bw_id = bw.id
        org.bw_active = "media"
        org.bw_name = "Test BW"
        db_session.commit()

        try:
            deleted_count = _remove_all_bw()

            assert deleted_count == 1
            assert db_session.query(BusinessWall).count() == 0
            assert user.selected_bw_id is None
            assert org.bw_id is None
            assert org.bw_active is None
            assert org.bw_name == ""
        finally:
            # _remove_all_bw commits; clean up the test user/org explicitly.
            db_session.delete(user)
            db_session.delete(org)
            db_session.commit()

    def test_remove_all_bw_no_records(self, db_session):
        """_remove_all_bw is a no-op when no BusinessWalls exist."""
        assert db_session.query(BusinessWall).count() == 0
        deleted_count = _remove_all_bw()
        assert deleted_count == 0
