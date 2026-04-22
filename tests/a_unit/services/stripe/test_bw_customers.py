# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for count_pr_bw_customers()."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Partnership,
    PartnershipStatus,
)
from app.modules.bw.bw_activation.models.business_wall import BWType
from app.services.stripe.bw_customers import count_pr_bw_customers

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user(db_session: Session, test_org: Organisation) -> User:
    """Create a test user."""
    user = User(email="test@example.com")
    db_session.add(user)
    db_session.flush()
    user.organisation_id = test_org.id
    db_session.flush()
    return user


@pytest.fixture
def pr_bw(db_session: Session, test_org: Organisation, test_user: User) -> BusinessWall:
    """Create an active PR BusinessWall."""
    bw = BusinessWall(
        bw_type=BWType.PR.value,
        status=BWStatus.ACTIVE.value,
        is_free=False,
        owner_id=test_user.id,
        payer_id=test_user.id,
        organisation_id=test_org.id,
        name="PR Agency BW",
    )
    db_session.add(bw)
    db_session.flush()
    return bw


@pytest.fixture
def client_bw(
    db_session: Session, test_org: Organisation, test_user: User
) -> BusinessWall:
    """Create an active media BusinessWall (client)."""
    bw = BusinessWall(
        bw_type=BWType.MEDIA.value,
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=test_user.id,
        payer_id=test_user.id,
        organisation_id=test_org.id,
        name="Client Media BW",
    )
    db_session.add(bw)
    db_session.flush()
    return bw


def _make_partnership(
    db_session: Session,
    client_bw: BusinessWall,
    pr_bw: BusinessWall,
    status: str,
    invited_by_user_id: int = 1,
) -> Partnership:
    """Helper to create a Partnership record."""
    p = Partnership(
        business_wall_id=client_bw.id,
        partner_bw_id=str(pr_bw.id),
        status=status,
        invited_by_user_id=invited_by_user_id,
    )
    db_session.add(p)
    db_session.flush()
    return p


class TestCountPrBwCustomers:
    """Test suite for count_pr_bw_customers."""

    def test_invalid_bw_id_returns_zero(self) -> None:
        """Non-UUID string."""
        assert count_pr_bw_customers("not-a-uuid") == 0

    def test_nonexistent_bw_returns_zero(self) -> None:
        """BW that does not exist should return 0."""
        assert count_pr_bw_customers(str(uuid4())) == 0

    def test_non_pr_bw_returns_zero(
        self, db_session: Session, test_org: Organisation, test_user: User
    ) -> None:
        """A media (so non PR) should return 0 customer."""
        media_bw = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            is_free=True,
            owner_id=test_user.id,
            payer_id=test_user.id,
            organisation_id=test_org.id,
        )
        db_session.add(media_bw)
        db_session.flush()

        assert count_pr_bw_customers(str(media_bw.id)) == 0

    def test_pr_bw_with_no_partnerships_returns_zero(self, pr_bw: BusinessWall) -> None:
        """PR BW without any partnerships should return 0."""
        assert count_pr_bw_customers(str(pr_bw.id)) == 0

    def test_pr_bw_with_one_active_partnership(
        self,
        db_session: Session,
        pr_bw: BusinessWall,
        client_bw: BusinessWall,
        test_user: User,
    ) -> None:
        """One active partnership should count as 1 customer."""
        _make_partnership(
            db_session,
            client_bw,
            pr_bw,
            PartnershipStatus.ACTIVE.value,
            test_user.id,
        )

        assert count_pr_bw_customers(str(pr_bw.id)) == 1

    def test_pr_bw_with_multiple_active_partnerships(
        self,
        db_session: Session,
        pr_bw: BusinessWall,
        test_org: Organisation,
        test_user: User,
    ) -> None:
        """Multiple active partnerships should all be counted."""
        for i in range(3):
            client = BusinessWall(
                bw_type=BWType.MEDIA.value,
                status=BWStatus.ACTIVE.value,
                is_free=True,
                owner_id=test_user.id,
                payer_id=test_user.id,
                organisation_id=test_org.id,
                name=f"Client {i}",
            )
            db_session.add(client)
            db_session.flush()
            _make_partnership(
                db_session,
                client,
                pr_bw,
                PartnershipStatus.ACTIVE.value,
                test_user.id,
            )

        assert count_pr_bw_customers(str(pr_bw.id)) == 3

    def test_invited_partnership_not_counted(
        self,
        db_session: Session,
        pr_bw: BusinessWall,
        client_bw: BusinessWall,
        test_user: User,
    ) -> None:
        """Invited partnerships should not count."""
        _make_partnership(
            db_session,
            client_bw,
            pr_bw,
            PartnershipStatus.INVITED.value,
            test_user.id,
        )

        assert count_pr_bw_customers(str(pr_bw.id)) == 0

    def test_rejected_partnership_not_counted(
        self,
        db_session: Session,
        pr_bw: BusinessWall,
        client_bw: BusinessWall,
        test_user: User,
    ) -> None:
        """Rejected partnerships should not count."""
        _make_partnership(
            db_session,
            client_bw,
            pr_bw,
            PartnershipStatus.REJECTED.value,
            test_user.id,
        )

        assert count_pr_bw_customers(str(pr_bw.id)) == 0

    def test_revoked_partnership_not_counted(
        self,
        db_session: Session,
        pr_bw: BusinessWall,
        client_bw: BusinessWall,
        test_user: User,
    ) -> None:
        """Revoked partnerships should not count."""
        _make_partnership(
            db_session,
            client_bw,
            pr_bw,
            PartnershipStatus.REVOKED.value,
            test_user.id,
        )

        assert count_pr_bw_customers(str(pr_bw.id)) == 0

    def test_expired_partnership_not_counted(
        self,
        db_session: Session,
        pr_bw: BusinessWall,
        client_bw: BusinessWall,
        test_user: User,
    ) -> None:
        """Expired partnerships should not count."""
        _make_partnership(
            db_session,
            client_bw,
            pr_bw,
            PartnershipStatus.EXPIRED.value,
            test_user.id,
        )

        assert count_pr_bw_customers(str(pr_bw.id)) == 0

    def test_accepted_partnership_is_counted(
        self,
        db_session: Session,
        pr_bw: BusinessWall,
        client_bw: BusinessWall,
        test_user: User,
    ) -> None:
        """Accepted partnerships should count."""
        _make_partnership(
            db_session,
            client_bw,
            pr_bw,
            PartnershipStatus.ACCEPTED.value,
            test_user.id,
        )

        assert count_pr_bw_customers(str(pr_bw.id)) == 1

    def test_mixed_statuses_only_counts_active_and_accepted(
        self,
        db_session: Session,
        pr_bw: BusinessWall,
        client_bw: BusinessWall,
        test_org: Organisation,
        test_user: User,
    ) -> None:
        """Only active and accepted partnerships should be counted."""
        # active – counted
        _make_partnership(
            db_session, client_bw, pr_bw, PartnershipStatus.ACTIVE.value, test_user.id
        )

        # accepted – counted
        client2 = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            is_free=True,
            owner_id=test_user.id,
            payer_id=test_user.id,
            organisation_id=test_org.id,
            name="Client 2",
        )
        db_session.add(client2)
        db_session.flush()
        _make_partnership(
            db_session,
            client2,
            pr_bw,
            PartnershipStatus.ACCEPTED.value,
            test_user.id,
        )

        # invited – NOT counted
        client3 = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            is_free=True,
            owner_id=test_user.id,
            payer_id=test_user.id,
            organisation_id=test_org.id,
            name="Client 3",
        )
        db_session.add(client3)
        db_session.flush()
        _make_partnership(
            db_session,
            client3,
            pr_bw,
            PartnershipStatus.INVITED.value,
            test_user.id,
        )

        # rejected – NOT counted
        client4 = BusinessWall(
            bw_type=BWType.MEDIA.value,
            status=BWStatus.ACTIVE.value,
            is_free=True,
            owner_id=test_user.id,
            payer_id=test_user.id,
            organisation_id=test_org.id,
            name="Client 4",
        )
        db_session.add(client4)
        db_session.flush()
        _make_partnership(
            db_session,
            client4,
            pr_bw,
            PartnershipStatus.REJECTED.value,
            test_user.id,
        )

        assert count_pr_bw_customers(str(pr_bw.id)) == 2
