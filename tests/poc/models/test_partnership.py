# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Partnership model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING


from poc.blueprints.bw_activation_full.models import Partnership, PartnershipRepository
from poc.blueprints.bw_activation_full.models import PartnershipStatus

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from poc.blueprints.bw_activation_full.models import BusinessWall


class TestPartnership:
    """Tests for Partnership model."""

    def test_create_partnership(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
        mock_org_id: int,
    ):
        """Test creating a Partnership."""
        partnership = Partnership(
            business_wall_id=business_wall.id,
            partner_org_id=mock_org_id,
            invited_by_user_id=mock_user_id,
            status=PartnershipStatus.INVITED.value,
            invitation_message="We'd like to work with your agency",
        )
        db_session.add(partnership)
        db_session.commit()

        assert partnership.id is not None
        assert partnership.business_wall_id == business_wall.id
        assert partnership.partner_org_id == mock_org_id
        assert partnership.invited_by_user_id == mock_user_id
        assert partnership.status == PartnershipStatus.INVITED.value
        assert partnership.invitation_message == "We'd like to work with your agency"

    def test_partnership_repr(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
        mock_org_id: int,
    ):
        """Test Partnership __repr__."""
        partnership = Partnership(
            business_wall_id=business_wall.id,
            partner_org_id=mock_org_id,
            invited_by_user_id=mock_user_id,
            status=PartnershipStatus.ACTIVE.value,
        )
        db_session.add(partnership)
        db_session.commit()

        repr_str = repr(partnership)
        assert "Partnership" in repr_str
        assert "active" in repr_str
        assert f"org_id={mock_org_id}" in repr_str

    def test_partnership_statuses(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
    ):
        """Test all partnership statuses."""
        statuses = [
            PartnershipStatus.INVITED,
            PartnershipStatus.ACCEPTED,
            PartnershipStatus.REJECTED,
            PartnershipStatus.ACTIVE,
            PartnershipStatus.REVOKED,
            PartnershipStatus.EXPIRED,
        ]

        for idx, status in enumerate(statuses):
            partnership = Partnership(
                business_wall_id=business_wall.id,
                partner_org_id=idx + 1,
                invited_by_user_id=mock_user_id,
                status=status.value,
            )
            db_session.add(partnership)

        db_session.commit()

        count = db_session.query(Partnership).count()
        assert count == len(statuses)

    def test_partnership_workflow(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
        mock_org_id: int,
    ):
        """Test partnership invitation and acceptance workflow."""
        partnership = Partnership(
            business_wall_id=business_wall.id,
            partner_org_id=mock_org_id,
            invited_by_user_id=mock_user_id,
            status=PartnershipStatus.INVITED.value,
            invitation_message="Let's collaborate",
            invited_at=datetime.now(timezone.utc),
        )
        db_session.add(partnership)
        db_session.commit()

        assert partnership.status == PartnershipStatus.INVITED.value
        assert partnership.invited_at is not None
        assert partnership.accepted_at is None

        # Accept partnership
        partnership.status = PartnershipStatus.ACCEPTED.value
        partnership.accepted_at = datetime.now(timezone.utc)
        db_session.commit()

        assert partnership.status == PartnershipStatus.ACCEPTED.value
        assert partnership.accepted_at is not None

        # Activate partnership
        partnership.status = PartnershipStatus.ACTIVE.value
        db_session.commit()

        assert partnership.status == PartnershipStatus.ACTIVE.value

    def test_partnership_rejection(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
        mock_org_id: int,
    ):
        """Test partnership rejection workflow."""
        partnership = Partnership(
            business_wall_id=business_wall.id,
            partner_org_id=mock_org_id,
            invited_by_user_id=mock_user_id,
            status=PartnershipStatus.INVITED.value,
            invited_at=datetime.now(timezone.utc),
        )
        db_session.add(partnership)
        db_session.commit()

        # Reject partnership
        partnership.status = PartnershipStatus.REJECTED.value
        partnership.rejected_at = datetime.now(timezone.utc)
        db_session.commit()

        assert partnership.status == PartnershipStatus.REJECTED.value
        assert partnership.rejected_at is not None

    def test_partnership_with_contract_terms(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
        mock_org_id: int,
    ):
        """Test partnership with contract terms."""
        start_date = datetime.now(timezone.utc)
        end_date = datetime(2025, 12, 31, tzinfo=timezone.utc)

        partnership = Partnership(
            business_wall_id=business_wall.id,
            partner_org_id=mock_org_id,
            invited_by_user_id=mock_user_id,
            status=PartnershipStatus.ACTIVE.value,
            contract_start_date=start_date,
            contract_end_date=end_date,
            notes="Annual contract with renewal option",
        )
        db_session.add(partnership)
        db_session.commit()

        assert partnership.contract_start_date == start_date
        assert partnership.contract_end_date == end_date
        assert partnership.notes == "Annual contract with renewal option"


class TestPartnershipRepository:
    """Tests for PartnershipRepository."""

    def test_repository_add(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
        mock_org_id: int,
    ):
        """Test repository add operation."""
        repo = PartnershipRepository(session=db_session)

        partnership = Partnership(
            business_wall_id=business_wall.id,
            partner_org_id=mock_org_id,
            invited_by_user_id=mock_user_id,
            status=PartnershipStatus.INVITED.value,
        )

        saved = repo.add(partnership)

        assert saved.id is not None
        assert saved.status == PartnershipStatus.INVITED.value

    def test_repository_get(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
        mock_org_id: int,
    ):
        """Test repository get operation."""
        repo = PartnershipRepository(session=db_session)

        partnership = Partnership(
            business_wall_id=business_wall.id,
            partner_org_id=mock_org_id,
            invited_by_user_id=mock_user_id,
            status=PartnershipStatus.ACTIVE.value,
        )
        repo.add(partnership)

        retrieved = repo.get(partnership.id)

        assert retrieved is not None
        assert retrieved.id == partnership.id
        assert retrieved.status == PartnershipStatus.ACTIVE.value

    def test_repository_update(
        self,
        db_session: Session,
        business_wall: BusinessWall,
        mock_user_id: int,
        mock_org_id: int,
    ):
        """Test repository update operation."""
        repo = PartnershipRepository(session=db_session)

        partnership = Partnership(
            business_wall_id=business_wall.id,
            partner_org_id=mock_org_id,
            invited_by_user_id=mock_user_id,
            status=PartnershipStatus.INVITED.value,
        )
        repo.add(partnership)

        # Update entity attributes
        partnership.status = PartnershipStatus.ACCEPTED.value
        updated = repo.update(partnership)

        assert updated.status == PartnershipStatus.ACCEPTED.value
