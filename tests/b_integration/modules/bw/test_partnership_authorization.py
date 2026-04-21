# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Partnership-aware publication authorization helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Partnership,
    PartnershipStatus,
)
from app.modules.bw.bw_activation.user_utils import (
    can_user_publish_for,
    get_representing_agency_org_ids_for_client,
    get_validated_client_orgs_for_user,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _mk_user_org_bw(
    db_session: Session, name: str, bw_type: str = "media"
) -> tuple[User, Organisation, BusinessWall]:
    """Create a User + Organisation + active BusinessWall triplet."""
    unique = uuid.uuid4().hex[:8]
    user = User(
        email=f"{name.lower()}-{unique}@example.com",
        first_name=name,
        last_name="Test",
        active=True,
    )
    db_session.add(user)
    db_session.flush()

    org = Organisation(name=f"{name} Org {unique}")
    db_session.add(org)
    db_session.flush()

    user.organisation = org
    user.organisation_id = org.id

    bw = BusinessWall(
        bw_type=bw_type,
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()

    org.bw_id = bw.id
    org.bw_active = bw_type
    db_session.flush()
    return user, org, bw


def _mk_partnership(
    db_session: Session,
    client_bw: BusinessWall,
    agency_bw: BusinessWall,
    status: PartnershipStatus,
) -> Partnership:
    """Link a client BW to an agency BW with a given Partnership status."""
    p = Partnership(
        business_wall_id=client_bw.id,
        partner_bw_id=str(agency_bw.id),
        status=status.value,
        invited_by_user_id=client_bw.owner_id,
        invited_at=datetime.now(UTC),
    )
    db_session.add(p)
    db_session.flush()
    return p


# ---------------------------------------------------------------------------
# get_validated_client_orgs_for_user
# ---------------------------------------------------------------------------


class TestGetValidatedClientOrgsForUser:
    def test_returns_empty_for_user_without_bw(self, db_session: Session):
        user = User(email="lonely@example.com", active=True)
        db_session.add(user)
        db_session.flush()

        assert get_validated_client_orgs_for_user(user) == []

    def test_returns_only_active_partnerships(self, db_session: Session):
        agency_user, _, agency_bw = _mk_user_org_bw(db_session, "Agency", "pr")
        _, client_a_org, client_a_bw = _mk_user_org_bw(db_session, "ClientA")
        _, _, client_b_bw = _mk_user_org_bw(db_session, "ClientB")
        _, _, client_c_bw = _mk_user_org_bw(db_session, "ClientC")

        _mk_partnership(
            db_session, client_a_bw, agency_bw, PartnershipStatus.ACTIVE
        )
        _mk_partnership(
            db_session, client_b_bw, agency_bw, PartnershipStatus.INVITED
        )
        _mk_partnership(
            db_session, client_c_bw, agency_bw, PartnershipStatus.REVOKED
        )

        orgs = get_validated_client_orgs_for_user(agency_user)

        org_ids = {o.id for o in orgs}
        assert org_ids == {client_a_org.id}

    def test_accepted_status_also_qualifies(self, db_session: Session):
        agency_user, _, agency_bw = _mk_user_org_bw(db_session, "Agency2", "pr")
        _, client_org, client_bw = _mk_user_org_bw(db_session, "ClientAccepted")
        _mk_partnership(
            db_session, client_bw, agency_bw, PartnershipStatus.ACCEPTED
        )

        orgs = get_validated_client_orgs_for_user(agency_user)

        assert [o.id for o in orgs] == [client_org.id]

    def test_ignores_partnerships_pointing_to_other_agency(
        self, db_session: Session
    ):
        agency_user, _, _ = _mk_user_org_bw(db_session, "AgencyA", "pr")
        _, _, other_agency_bw = _mk_user_org_bw(db_session, "AgencyB", "pr")
        _, _, client_bw = _mk_user_org_bw(db_session, "ClientShared")

        _mk_partnership(
            db_session, client_bw, other_agency_bw, PartnershipStatus.ACTIVE
        )

        assert get_validated_client_orgs_for_user(agency_user) == []


# ---------------------------------------------------------------------------
# can_user_publish_for
# ---------------------------------------------------------------------------


class TestCanUserPublishFor:
    def test_allows_publishing_for_own_organisation(self, db_session: Session):
        user, org, _ = _mk_user_org_bw(db_session, "SelfPub")
        assert can_user_publish_for(user, org.id) is True

    def test_allows_publishing_for_validated_client(self, db_session: Session):
        agency_user, _, agency_bw = _mk_user_org_bw(db_session, "AgencyOK", "pr")
        _, client_org, client_bw = _mk_user_org_bw(db_session, "ClientValid")
        _mk_partnership(
            db_session, client_bw, agency_bw, PartnershipStatus.ACTIVE
        )

        assert can_user_publish_for(agency_user, client_org.id) is True

    def test_rejects_publishing_for_unknown_org(self, db_session: Session):
        agency_user, _, _ = _mk_user_org_bw(db_session, "AgencyReject", "pr")
        _, stranger_org, _ = _mk_user_org_bw(db_session, "Stranger")

        assert can_user_publish_for(agency_user, stranger_org.id) is False

    def test_rejects_publishing_for_revoked_client(self, db_session: Session):
        agency_user, _, agency_bw = _mk_user_org_bw(db_session, "AgencyRevk", "pr")
        _, client_org, client_bw = _mk_user_org_bw(db_session, "ClientRevoked")
        _mk_partnership(
            db_session, client_bw, agency_bw, PartnershipStatus.REVOKED
        )

        assert can_user_publish_for(agency_user, client_org.id) is False


# ---------------------------------------------------------------------------
# get_representing_agency_org_ids_for_client
# ---------------------------------------------------------------------------


class TestGetRepresentingAgencyOrgIds:
    def test_returns_empty_when_org_has_no_bw(self, db_session: Session):
        org = Organisation(name="No BW Org")
        db_session.add(org)
        db_session.flush()

        assert get_representing_agency_org_ids_for_client(org) == []

    def test_returns_agency_ids_for_active_partnerships(
        self, db_session: Session
    ):
        _, _, agency_bw = _mk_user_org_bw(db_session, "AgencyRep", "pr")
        agency_org_id = agency_bw.organisation_id
        _, client_org, client_bw = _mk_user_org_bw(db_session, "ClientRep")

        _mk_partnership(
            db_session, client_bw, agency_bw, PartnershipStatus.ACTIVE
        )

        assert get_representing_agency_org_ids_for_client(client_org) == [
            agency_org_id
        ]

    def test_excludes_non_active_partnerships(self, db_session: Session):
        _, _, agency_bw = _mk_user_org_bw(db_session, "AgencyInvited", "pr")
        _, client_org, client_bw = _mk_user_org_bw(db_session, "ClientInvited")

        _mk_partnership(
            db_session, client_bw, agency_bw, PartnershipStatus.INVITED
        )

        assert get_representing_agency_org_ids_for_client(client_org) == []


# ---------------------------------------------------------------------------
# Exercises the SQL query (imports for the SELECT live in the helper)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", [PartnershipStatus.ACTIVE, PartnershipStatus.ACCEPTED])
def test_query_shapes_work_against_db(
    db_session: Session, status: PartnershipStatus
):
    """Guards against regressions in SQL type-casting (UUID <-> String)."""
    agency_user, _, agency_bw = _mk_user_org_bw(db_session, f"A-{status.value}", "pr")
    _, client_org, client_bw = _mk_user_org_bw(db_session, f"C-{status.value}")
    _mk_partnership(db_session, client_bw, agency_bw, status)

    assert client_org in get_validated_client_orgs_for_user(agency_user)
    assert can_user_publish_for(agency_user, client_org.id) is True
