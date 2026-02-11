# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for BusinessWall model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from advanced_alchemy.exceptions import NotFoundError
from poc.blueprints.bw_activation_full.models import (
    BusinessWallPoc,
    BusinessWallPocRepository,
    BWStatus,
    BWType,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestBusinessWallPoc:
    """Tests for BusinessWallPoc model."""

    def test_create_business_wall(self, db_session: Session, mock_user_id: int):
        """Test creating a BusinessWallPoc."""
        bw = BusinessWallPoc(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            is_free=True,
            owner_id=mock_user_id,
            payer_id=mock_user_id,
        )
        db_session.add(bw)
        db_session.commit()

        assert bw.id is not None
        assert bw.bw_type == "media"
        assert bw.status == "draft"
        assert bw.is_free is True
        assert bw.owner_id == mock_user_id
        assert bw.payer_id == mock_user_id
        assert bw.created_at is not None
        assert bw.updated_at is not None

    def test_business_wall_repr(self, business_wall: BusinessWallPoc):
        """Test BusinessWallPoc __repr__."""
        repr_str = repr(business_wall)
        assert "BusinessWallPoc" in repr_str
        assert "media" in repr_str
        assert "draft" in repr_str

    def test_business_wall_types(self, db_session: Session, mock_user_id: int):
        """Test all BusinessWallPoc types can be created."""
        types = [
            BWType.MEDIA,
            BWType.MICRO,
            BWType.CORPORATE_MEDIA,
            BWType.UNION,
            BWType.ACADEMICS,
            BWType.PR,
            BWType.LEADERS_EXPERTS,
            BWType.TRANSFORMERS,
        ]

        for bw_type in types:
            bw = BusinessWallPoc(
                bw_type=bw_type.value,
                status=BWStatus.DRAFT.value,
                is_free=True,
                owner_id=mock_user_id,
                payer_id=mock_user_id,
            )
            db_session.add(bw)

        db_session.commit()

        count = db_session.query(BusinessWallPoc).count()
        assert count == len(types)

    def test_business_wall_status_transitions(
        self, db_session: Session, business_wall: BusinessWallPoc
    ):
        """Test status transitions."""
        assert business_wall.status == BWStatus.DRAFT.value

        # Draft -> Active
        business_wall.status = BWStatus.ACTIVE.value
        business_wall.activated_at = datetime.now(timezone.utc)
        db_session.commit()

        assert business_wall.status == BWStatus.ACTIVE.value
        assert business_wall.activated_at is not None

        # Active -> Suspended
        business_wall.status = BWStatus.SUSPENDED.value
        db_session.commit()

        assert business_wall.status == BWStatus.SUSPENDED.value

    def test_business_wall_with_different_payer(
        self, db_session: Session, mock_user_id: int, mock_payer_id: int
    ):
        """Test BusinessWallPoc with different owner and payer."""
        bw = BusinessWallPoc(
            bw_type=BWType.PR.value,
            status=BWStatus.DRAFT.value,
            is_free=False,
            owner_id=mock_user_id,
            payer_id=mock_payer_id,
        )
        db_session.add(bw)
        db_session.commit()

        assert bw.owner_id == mock_user_id
        assert bw.payer_id == mock_payer_id
        assert bw.owner_id != bw.payer_id

    def test_business_wall_with_organisation(
        self, db_session: Session, mock_user_id: int, mock_org_id: int
    ):
        """Test BusinessWallPoc with organisation reference."""
        bw = BusinessWallPoc(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            is_free=True,
            owner_id=mock_user_id,
            payer_id=mock_user_id,
            organisation_id=mock_org_id,
        )
        db_session.add(bw)
        db_session.commit()

        assert bw.organisation_id == mock_org_id


class TestBusinessWallPocRepository:
    """Tests for BusinessWallPocRepository."""

    def test_repository_add(self, db_session: Session, mock_user_id: int):
        """Test repository add operation."""
        repo = BusinessWallPocRepository(session=db_session)

        bw = BusinessWallPoc(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.DRAFT.value,
            is_free=True,
            owner_id=mock_user_id,
            payer_id=mock_user_id,
        )

        saved_bw = repo.add(bw)

        assert saved_bw.id is not None
        assert saved_bw.bw_type == "media"

    def test_repository_get(self, db_session: Session, business_wall: BusinessWallPoc):
        """Test repository get operation."""
        repo = BusinessWallPocRepository(session=db_session)

        retrieved = repo.get(business_wall.id)

        assert retrieved is not None
        assert retrieved.id == business_wall.id
        assert retrieved.bw_type == business_wall.bw_type

    def test_repository_list(
        self, db_session: Session, mock_user_id: int, business_wall: BusinessWallPoc
    ):
        """Test repository list operation."""
        repo = BusinessWallPocRepository(session=db_session)

        # Create another BW
        bw2 = BusinessWallPoc(
            bw_type=BWType.PR.value,
            status=BWStatus.ACTIVE.value,
            is_free=False,
            owner_id=mock_user_id,
            payer_id=mock_user_id,
        )
        repo.add(bw2)

        # List all
        all_bws = repo.list()
        assert len(all_bws) == 2

    def test_repository_update(
        self, db_session: Session, business_wall: BusinessWallPoc
    ):
        """Test repository update operation."""
        repo = BusinessWallPocRepository(session=db_session)

        # Update entity attributes
        business_wall.status = BWStatus.ACTIVE.value
        updated = repo.update(business_wall)

        assert updated.status == BWStatus.ACTIVE.value

    def test_repository_delete(
        self, db_session: Session, business_wall: BusinessWallPoc
    ):
        """Test repository delete operation."""
        repo = BusinessWallPocRepository(session=db_session)

        bw_id = business_wall.id
        repo.delete(bw_id)

        # Advanced-Alchemy's get() raises NotFoundError instead of returning None
        with pytest.raises(NotFoundError):
            repo.get(bw_id)
