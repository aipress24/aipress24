# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for preferences invitations views."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from uuid import UUID

import pytest
from sqlalchemy import select

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.invitations import add_invited_users
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    InvitationStatus,
    Partnership,
    PartnershipStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.preferences.views.invitations import InvitationsView
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_inviting_user_with_profile(db_session: Session) -> User:
    """Create a test user with profile managing a BW."""
    user = User(email="inviting_user@example.com")
    user.first_name = "Test"
    user.last_name = "User"
    user.active = True
    user.photo = b""

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def invitations_test_user(db_session: Session) -> User:
    """Create a test user for invitations tests.

    Invitation must be sent for an organisation with an active BW."""
    unique_id = uuid.uuid4().hex[:8]

    # Create role
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.flush()

    # Create organisation for user
    org = Organisation(name=f"Test Auto Org {unique_id}")
    db_session.add(org)
    db_session.flush()

    user = User(email=f"invit-test-{unique_id}@example.com")
    user.first_name = "Invit"
    user.last_name = "Test"
    user.photo = b""
    user.organisation = org
    user.active = True
    user.roles.append(role)

    profile = KYCProfile(contact_type="PRESSE", match_making={})
    user.profile = profile

    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def invitations_auth_client(app: Flask, invitations_test_user: User) -> FlaskClient:
    """Provide an authenticated client for invitations tests."""
    return make_authenticated_client(app, invitations_test_user)


@pytest.fixture
def inviting_org(
    db_session: Session, test_inviting_user_with_profile: User
) -> Organisation:
    """Create an organization that sends invitations.

    Invitation must be sent for an organisation with an active BW."""
    org = Organisation(name="Inviting Organisation")
    db_session.add(org)
    db_session.flush()

    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=test_inviting_user_with_profile.id,
        payer_id=test_inviting_user_with_profile.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Link organisation to BW
    org.bw_id = bw.id
    org.bw_active = bw.bw_type
    org.bw_name = org.name
    db_session.flush()

    return org


@pytest.fixture
def invitation_for_user(
    db_session: Session, invitations_test_user: User, inviting_org: Organisation
) -> Invitation:
    """Create an invitation for the test user."""
    invitation = Invitation(
        email=invitations_test_user.email,
        organisation_id=inviting_org.id,
    )
    db_session.add(invitation)
    db_session.flush()
    return invitation


class TestInvitationsView:
    """Tests for InvitationsView."""

    def test_invitations_page_loads(
        self, invitations_auth_client: FlaskClient, invitations_test_user: User
    ):
        """Test invitations page loads successfully."""
        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200

    def test_invitations_page_shows_title(
        self, invitations_auth_client: FlaskClient, invitations_test_user: User
    ):
        """Test invitations page shows correct title."""
        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200
        html = response.data.decode()
        assert "invitation" in html.lower() or "organisation" in html.lower()

    def test_invitations_with_invitation(
        self,
        invitations_auth_client: FlaskClient,
        invitations_test_user: User,
        invitation_for_user: Invitation,
        inviting_org: Organisation,
    ):
        """Test invitations page shows inviting organization."""
        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200
        html = response.data.decode()
        assert inviting_org.bw_name in html


class TestInvitationsEmailNormalisation:
    """Bug 0130: invitations failed to surface when the stored email differed
    from `user.email` only by case or surrounding whitespace.

    Storage now lower-cases + strips at write time (`add_invited_users`) and
    the lookup in `_organisation_inviting` mirrors the same normalisation
    (`func.lower(func.trim(...))`)."""

    def _make_invitation(
        self, db_session: Session, raw_email: str, org: Organisation
    ) -> Invitation:
        """Insert an Invitation row with the raw email AS-IS (bypasses
        add_invited_users so we can test the lookup against legacy data)."""
        invitation = Invitation(email=raw_email, organisation_id=org.id)
        db_session.add(invitation)
        db_session.flush()
        return invitation

    def test_invitation_with_uppercase_stored_email_matches_lowercase_user(
        self,
        db_session: Session,
        invitations_test_user: User,
        inviting_org: Organisation,
    ):
        """Stored "USER@EXAMPLE.COM", user.email "user@example.com" → match."""
        upper = invitations_test_user.email.upper()
        self._make_invitation(db_session, upper, inviting_org)

        view = InvitationsView()
        result = view._organisation_inviting(invitations_test_user)

        org_ids = [r["org_id"] for r in result]
        assert str(inviting_org.id) in org_ids

    def test_invitation_with_whitespace_around_email_still_matches(
        self,
        db_session: Session,
        invitations_test_user: User,
        inviting_org: Organisation,
    ):
        """Stored "  user@example.com  " must still match user.email."""
        padded = f"  {invitations_test_user.email}  "
        self._make_invitation(db_session, padded, inviting_org)

        view = InvitationsView()
        result = view._organisation_inviting(invitations_test_user)

        org_ids = [r["org_id"] for r in result]
        assert str(inviting_org.id) in org_ids

    def test_add_invited_users_normalises_at_storage(
        self, db_session: Session, inviting_org: Organisation
    ):
        """add_invited_users() must store a normalised (lowercase + stripped)
        email, regardless of the casing/spacing the inviter used."""
        appended = add_invited_users(
            ["  Olivia.Buzzatti@Example.COM  "], inviting_org.id
        )

        assert appended == ["olivia.buzzatti@example.com"]

        stored = db_session.scalar(
            select(Invitation).where(Invitation.organisation_id == inviting_org.id)
        )
        assert stored is not None
        assert stored.email == "olivia.buzzatti@example.com"


class TestInvitationsViewHelpers:
    """Tests for InvitationsView helper methods."""

    def test_organisation_inviting_no_org_no_invit(self, app: Flask):
        """Test _organisation_inviting returns empty list when no org and no invit."""
        view = InvitationsView()
        user = MagicMock()
        user.organisation = None
        user.email = "test@example.com"

        with app.app_context():
            result = view._organisation_inviting(user)
            assert result == []

    def test_organisation_inviting_with_org_no_invit(self, app: Flask):
        """Test _organisation_inviting returns current org when no invit."""
        view = InvitationsView()
        user = MagicMock()
        org = MagicMock()
        org.id = 123
        org.name = "My Org"
        org.bw_id = None
        user.organisation = org
        user.organisation_id = 123
        user.email = "test@example.com"

        with app.app_context():
            result = view._organisation_inviting(user)
            assert len(result) == 1
            assert result[0]["org_id"] == "123"
            assert result[0]["disabled"] == "disabled"
            assert "My Org" in result[0]["label"]


class TestInvitationsPageModalIds:
    """Regression for commit 9adc1623 (Jérôme, 2026-05-26).

    Before the fix, every « Rejoindre » button shared
    ``data-modal-target="confirm_join_org"`` and every confirmation
    modal shared ``id="confirm_join_org"``. With ≥ 2 invitations the
    duplicate HTML ids meant only the first modal worked — clicking the
    second « Rejoindre » either did nothing or pointed at the wrong org.
    Fix : suffix the id with ``{{ loop.index }}``.
    """

    def _make_inviting_org(
        self, db_session: Session, owner: User, name: str
    ) -> Organisation:
        org = Organisation(name=name)
        db_session.add(org)
        db_session.flush()
        bw = BusinessWall(
            bw_type="media",
            status=BWStatus.ACTIVE.value,
            owner_id=owner.id,
            payer_id=owner.id,
            organisation_id=org.id,
        )
        db_session.add(bw)
        db_session.flush()
        org.bw_id = bw.id
        org.bw_active = bw.bw_type
        org.bw_name = name
        db_session.flush()
        return org

    def test_each_invitation_has_a_unique_modal_id(
        self,
        db_session: Session,
        invitations_auth_client: FlaskClient,
        invitations_test_user: User,
        test_inviting_user_with_profile: User,
    ):
        """With two pending invitations the page must render two
        distinct modal ids and two distinct ``data-modal-target``
        attributes, pairwise consistent."""
        org_a = self._make_inviting_org(
            db_session, test_inviting_user_with_profile, "Inviter A"
        )
        org_b = self._make_inviting_org(
            db_session, test_inviting_user_with_profile, "Inviter B"
        )
        for org in (org_a, org_b):
            db_session.add(
                Invitation(
                    email=invitations_test_user.email,
                    organisation_id=org.id,
                )
            )
        db_session.flush()

        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200
        html = response.data.decode()

        modal_ids = re.findall(r'id="(confirm_join_org_\d+)"', html)
        modal_targets = re.findall(r'data-modal-target="(confirm_join_org_\d+)"', html)

        assert len(modal_ids) == 2, (
            f"expected 2 distinct confirm-join modals, got {len(modal_ids)} : "
            f"{modal_ids}"
        )
        assert len(set(modal_ids)) == 2, (
            f"modal ids must be distinct, got duplicates : {modal_ids}"
        )
        # Every button's target must point at one of the rendered modals.
        for target in modal_targets:
            assert target in modal_ids, (
                f"data-modal-target {target!r} does not match any modal id "
                f"in the rendered page"
            )


class TestInvitationsViewDedup:
    """Regression for commit 96c67803 (Jérôme, 2026-05-26).

    Before the fix, when an Invitation existed for the user's *own*
    current organisation, `_organisation_inviting` returned both : one
    row for « current org » (disabled) and one row for « invitation to
    join » (enabled). The screen then offered the user to « rejoindre »
    an org they were already a member of. The fix removes the current
    org id from the invitation set before listing the remaining
    invitations.
    """

    def test_current_org_appears_once_when_invited_to_own_org(
        self,
        db_session: Session,
        invitations_test_user: User,
    ):
        """An invitation pointing at user.organisation must not produce a
        duplicate row in the invitations list."""
        own_org = invitations_test_user.organisation
        assert own_org is not None

        # Inject a fresh invitation pointing at the user's own org.
        invitation = Invitation(
            email=invitations_test_user.email,
            organisation_id=own_org.id,
        )
        db_session.add(invitation)
        db_session.flush()

        view = InvitationsView()
        result = view._organisation_inviting(invitations_test_user)

        own_id = str(own_org.id)
        own_rows = [r for r in result if r["org_id"] == own_id]
        assert len(own_rows) == 1, (
            "user's own organisation must appear exactly once in the "
            "invitations list, even when an invitation row points at it "
            "(#96c67803)"
        )
        assert own_rows[0]["disabled"] == "disabled", (
            "the single row for the user's own org must be the disabled "
            "« current org » entry, not an actionable « join » entry"
        )

    def test_invitation_to_other_org_still_listed_alongside_current_org(
        self,
        db_session: Session,
        invitations_test_user: User,
        inviting_org: Organisation,
        invitation_for_user: Invitation,
    ):
        """The dedup must not over-trim : a real invitation to a different
        org must still appear, in addition to the user's current org row.
        """
        own_org = invitations_test_user.organisation
        assert own_org is not None
        assert inviting_org.id != own_org.id

        view = InvitationsView()
        result = view._organisation_inviting(invitations_test_user)

        org_ids = [r["org_id"] for r in result]
        assert str(own_org.id) in org_ids
        assert str(inviting_org.id) in org_ids

        # The current-org row stays disabled ; the foreign-org row is
        # actionable (empty "disabled" string).
        for row in result:
            if row["org_id"] == str(own_org.id):
                assert row["disabled"] == "disabled"
            elif row["org_id"] == str(inviting_org.id):
                assert row["disabled"] == ""


class TestRevokedPartnershipRow:
    """Ticket #0169 part 3 (Erick, 2026-05-22) : when a client revokes
    a PR partnership, the PR Agency owner must see an explicit row in
    /preferences/invitations naming the client, with a « Confirmer »
    button that hard-deletes the row (Erick : « éliminer cette ligne »).
    """

    @pytest.fixture
    def revoked_partnership_setup(
        self,
        db_session: Session,
        invitations_test_user: User,
    ) -> tuple[BusinessWall, Partnership]:
        """Build : a PR Agency BW owned by the test user + a client BW
        owned by someone else + a Partnership in REVOKED status."""
        # Client org + BW (the side that revoked).
        client_org = Organisation(name="Fake-Davi Logistique")
        db_session.add(client_org)
        db_session.flush()
        client_owner = User(email=f"client-owner-{uuid.uuid4().hex[:6]}@example.com")
        client_owner.organisation = client_org
        client_owner.active = True
        db_session.add(client_owner)
        db_session.flush()
        client_bw = BusinessWall(
            bw_type="leaders_experts",
            status=BWStatus.ACTIVE.value,
            owner_id=client_owner.id,
            payer_id=client_owner.id,
            organisation_id=client_org.id,
            name="Davi Logistique BW",
        )
        db_session.add(client_bw)
        db_session.flush()
        client_org.bw_id = client_bw.id

        # Agency BW for the test user (who is the PR Agency owner).
        agency_bw = BusinessWall(
            bw_type="pr",
            status=BWStatus.ACTIVE.value,
            owner_id=invitations_test_user.id,
            payer_id=invitations_test_user.id,
            organisation_id=invitations_test_user.organisation_id,
            name="Test Agency BW",
        )
        db_session.add(agency_bw)
        db_session.flush()

        partnership = Partnership(
            business_wall_id=client_bw.id,
            partner_bw_id=str(agency_bw.id),
            status=PartnershipStatus.REVOKED.value,
            invited_by_user_id=client_owner.id,
            invited_at=datetime.now(UTC),
            revoked_at=datetime.now(UTC),
        )
        db_session.add(partnership)
        db_session.commit()
        return client_bw, partnership

    def test_revoked_partnership_row_visible(
        self,
        invitations_auth_client: FlaskClient,
        revoked_partnership_setup: tuple,
    ):
        """GET /preferences/invitations surfaces the revoked row with
        the client org name."""
        _client_bw, _partnership = revoked_partnership_setup
        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Partenariats RP terminés" in html
        assert "Fake-Davi Logistique" in html
        assert "Confirmer" in html

    def test_confirm_deletes_revoked_partnership_row(
        self,
        invitations_auth_client: FlaskClient,
        revoked_partnership_setup: tuple,
        db_session: Session,
    ):
        """POST action=ack_revoked_partnership hard-deletes the row."""
        _client_bw, partnership = revoked_partnership_setup
        partnership_id = str(partnership.id)

        response = invitations_auth_client.post(
            "/preferences/invitations",
            data={
                "action": "ack_revoked_partnership",
                "partnership_id": partnership_id,
            },
            follow_redirects=False,
        )
        # Ticket #0169: the « Confirmer » button is a plain <form> POST, so
        # the handler must return a real 302 (not Response('')+HX-Redirect,
        # which a non-htmx form ignores → blank page).
        assert response.status_code == 302
        assert "/preferences/invitations" in response.headers["Location"]
        # The Partnership row is gone.
        assert db_session.get(Partnership, UUID(partnership_id)) is None

    def test_confirm_flashes_success_message(
        self,
        invitations_auth_client: FlaskClient,
        revoked_partnership_setup: tuple,
    ):
        """Bug #0169 (réouvert 2026-06-02) — Erick : « lorsque Marc
        Rodriguez appuie sur le bouton "Confirmé", il tombe sur une
        page blanche qui n'a pas de sens. Il faudrait mettre quelque
        chose du genre "Votre confirmation de fin de partenariat est
        bien enregistrée" ». Le POST ack_revoked_partnership doit
        flasher un message de succès stocké en session, qui sera
        rendu par le frontend sur le GET suivant via window.toasts."""
        _client_bw, partnership = revoked_partnership_setup
        partnership_id = str(partnership.id)

        invitations_auth_client.post(
            "/preferences/invitations",
            data={
                "action": "ack_revoked_partnership",
                "partnership_id": partnership_id,
            },
            follow_redirects=False,
        )

        # Inspect the test-client session — `flash()` populates
        # session["_flashes"] which the next request's template will
        # consume via get_flashed_messages().
        with invitations_auth_client.session_transaction() as sess:
            flashes = sess.get("_flashes") or []
            messages = [msg for _category, msg in flashes]
            assert any(
                "Votre confirmation de fin de partenariat est bien enregistrée" in m
                for m in messages
            ), f"expected success flash, got {flashes!r}"

    def test_confirm_refuses_partnership_not_owned_by_user(
        self,
        invitations_auth_client: FlaskClient,
        db_session: Session,
    ):
        """A user cannot ack a partnership where their org isn't on
        the partner side (would let them delete arbitrary rows)."""
        other_owner = User(email=f"other-{uuid.uuid4().hex[:6]}@example.com")
        other_org = Organisation(name="Other PR Agency")
        db_session.add(other_org)
        db_session.flush()
        other_owner.organisation = other_org
        other_owner.active = True
        client_owner = User(email=f"client-{uuid.uuid4().hex[:6]}@example.com")
        client_org = Organisation(name="Other Client")
        db_session.add(client_org)
        db_session.flush()
        client_owner.organisation = client_org
        client_owner.active = True
        db_session.add_all([other_owner, client_owner])
        db_session.flush()

        other_bw = BusinessWall(
            bw_type="pr",
            status=BWStatus.ACTIVE.value,
            owner_id=other_owner.id,
            payer_id=other_owner.id,
            organisation_id=other_org.id,
        )
        client_bw = BusinessWall(
            bw_type="leaders_experts",
            status=BWStatus.ACTIVE.value,
            owner_id=client_owner.id,
            payer_id=client_owner.id,
            organisation_id=client_org.id,
        )
        db_session.add_all([other_bw, client_bw])
        db_session.flush()

        partnership = Partnership(
            business_wall_id=client_bw.id,
            partner_bw_id=str(other_bw.id),  # NOT the test user's BW
            status=PartnershipStatus.REVOKED.value,
            invited_by_user_id=client_owner.id,
            invited_at=datetime.now(UTC),
            revoked_at=datetime.now(UTC),
        )
        db_session.add(partnership)
        db_session.commit()
        partnership_id = str(partnership.id)

        invitations_auth_client.post(
            "/preferences/invitations",
            data={
                "action": "ack_revoked_partnership",
                "partnership_id": partnership_id,
            },
            follow_redirects=False,
        )

        assert db_session.get(Partnership, UUID(partnership_id)) is not None, (
            "user must not be able to delete a partnership their org doesn't own"
        )


class TestInvitationsJoinOrg:
    """Tests for joining organization via invitations."""

    def test_join_org_action(
        self,
        invitations_auth_client: FlaskClient,
        invitations_test_user: User,
        invitation_for_user: Invitation,
        inviting_org: Organisation,
        db_session: Session,
    ):
        """Test join_org action redirects."""
        response = invitations_auth_client.post(
            "/preferences/invitations",
            data={
                "action": "join_org",
                "target": str(inviting_org.id),
            },
            follow_redirects=False,
        )
        assert response.status_code == 200
        assert "HX-Redirect" in response.headers


class TestInvitationsJoinOrgRequiresInvitation:
    """Security review VERIFY-001 — `_join_organisation` must verify
    that the user has a matching `Invitation` row for the requested
    org id before mutating `user.organisation`. Without this check,
    any authenticated user can POST `action=join_org&target=<any_org>`
    and become a member of an arbitrary organisation."""

    def test_join_org_refuses_without_invitation(
        self,
        invitations_auth_client: FlaskClient,
        invitations_test_user: User,
        db_session: Session,
    ):
        """The user has NO invitation for `target_org`. The POST must
        not change `user.organisation_id`."""
        # An org the user was NEVER invited to.
        target_org = Organisation(name="Forbidden Org")
        db_session.add(target_org)
        db_session.flush()

        original_org_id = invitations_test_user.organisation_id
        assert target_org.id != original_org_id

        invitations_auth_client.post(
            "/preferences/invitations",
            data={
                "action": "join_org",
                "target": str(target_org.id),
            },
            follow_redirects=False,
        )

        db_session.refresh(invitations_test_user)
        assert invitations_test_user.organisation_id == original_org_id, (
            "user must not become a member of an org they were never "
            "invited to (VERIFY-001)"
        )
        assert invitations_test_user.organisation_id != target_org.id

    def test_join_org_still_works_with_matching_invitation(
        self,
        invitations_auth_client: FlaskClient,
        invitations_test_user: User,
        invitation_for_user: Invitation,
        inviting_org: Organisation,
        db_session: Session,
    ):
        """Regression : with a real invitation row, joining still
        works (the fix must not break the legitimate flow)."""
        original_org_id = invitations_test_user.organisation_id
        assert inviting_org.id != original_org_id

        response = invitations_auth_client.post(
            "/preferences/invitations",
            data={
                "action": "join_org",
                "target": str(inviting_org.id),
            },
            follow_redirects=False,
        )

        assert response.status_code == 200
        db_session.refresh(invitations_test_user)
        assert invitations_test_user.organisation_id == inviting_org.id


class TestLeaveOrganisation:
    """Ticket #0228 — a member who accepted an org invitation by mistake
    must be able to leave (remove themselves from the organisation)."""

    @staticmethod
    def _member(db_session: Session, org: Organisation) -> User:
        profile = KYCProfile(contact_type="PRESSE")
        profile.show_contact_details = {}
        user = User(
            email=f"leave_{uuid.uuid4().hex[:6]}@example.com",
            first_name="L",
            last_name="Member",
            active=True,
        )
        user.organisation_id = org.id
        user.profile = profile
        db_session.add_all([user, profile])
        db_session.commit()
        return user

    def test_leave_org_removes_membership(self, app: Flask, db_session: Session):
        org = Organisation(name=f"Org-{uuid.uuid4().hex[:6]}")
        db_session.add(org)
        db_session.flush()
        user = self._member(db_session, org)

        client = make_authenticated_client(app, user)
        response = client.post(
            "/preferences/invitations",
            data={"action": "leave_org", "target": str(org.id)},
            follow_redirects=False,
        )

        assert response.status_code == 200
        db_session.refresh(user)
        assert user.organisation_id is None

    def test_leave_org_ignores_a_forged_target(self, app: Flask, db_session: Session):
        org = Organisation(name=f"Mine-{uuid.uuid4().hex[:6]}")
        other = Organisation(name=f"Other-{uuid.uuid4().hex[:6]}")
        db_session.add_all([org, other])
        db_session.flush()
        user = self._member(db_session, org)

        client = make_authenticated_client(app, user)
        # A target that isn't the user's own org must be a no-op.
        client.post(
            "/preferences/invitations",
            data={"action": "leave_org", "target": str(other.id)},
            follow_redirects=False,
        )

        db_session.refresh(user)
        assert user.organisation_id == org.id


class TestAcceptedRoleStaysVisible:
    """Bug: a BW role (e.g. BWPRi) that the user accepted vanished from
    /preferences/invitations because the page only listed PENDING role
    assignments. Once accepted the role still exists in DB but the user
    perceived it as "lost". The accepted role must stay visible."""

    @pytest.fixture
    def accepted_role_for_user(
        self,
        db_session: Session,
        invitations_test_user: User,
        inviting_org: Organisation,
    ) -> RoleAssignment:
        """An ACCEPTED BWPRi role assignment for the test user."""
        bw = db_session.scalar(
            select(BusinessWall).where(BusinessWall.id == inviting_org.bw_id)
        )
        assert bw is not None
        role = RoleAssignment(
            business_wall_id=bw.id,
            user_id=invitations_test_user.id,
            role_type="BWPRi",
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.flush()
        return role

    def test_accepted_role_listed_by_helper(
        self,
        invitations_test_user: User,
        accepted_role_for_user: RoleAssignment,
    ):
        """The view exposes accepted role assignments, not only pending ones."""
        view = InvitationsView()
        accepted = view._accepted_role_invitations(invitations_test_user)

        role_types = [r["role_type"] for r in accepted]
        assert "BWPRi" in role_types

    def test_accepted_role_visible_on_page(
        self,
        invitations_auth_client: FlaskClient,
        invitations_test_user: User,
        accepted_role_for_user: RoleAssignment,
        inviting_org: Organisation,
    ):
        """An accepted role still shows up on the invitations page."""
        response = invitations_auth_client.get("/preferences/invitations")
        assert response.status_code == 200
        html = response.data.decode()
        assert "PR Manager (internal)" in html
        assert inviting_org.bw_name in html

    def test_cancelled_bw_role_is_hidden(
        self,
        db_session: Session,
        invitations_test_user: User,
        inviting_org: Organisation,
        test_inviting_user_with_profile: User,
    ):
        """Bug #0139 (constat B) : un rôle accepté sur un BW
        *cancelled* (itération antérieure d'un BW recréé depuis) ne
        doit plus apparaître dans le profil — sinon l'utilisateur voit
        des duplicats fantômes (« 2× PR Manager interne », trace d'un
        BWO d'une iteration passée, etc.)."""
        # BW actif (déjà fourni par `inviting_org`)
        active_bw = db_session.scalar(
            select(BusinessWall).where(BusinessWall.id == inviting_org.bw_id)
        )
        assert active_bw is not None
        db_session.add(
            RoleAssignment(
                business_wall_id=active_bw.id,
                user_id=invitations_test_user.id,
                role_type="BWPRi",
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
        # BW cancelled (vestige d'une itération antérieure de la même
        # org, avec un rôle accepté qui ne devrait plus être listé)
        cancelled_bw = BusinessWall(
            bw_type="media",
            status=BWStatus.CANCELLED.value,
            owner_id=test_inviting_user_with_profile.id,
            payer_id=test_inviting_user_with_profile.id,
            organisation_id=inviting_org.id,
            name="Vestige BW cancelled",
        )
        db_session.add(cancelled_bw)
        db_session.flush()
        db_session.add(
            RoleAssignment(
                business_wall_id=cancelled_bw.id,
                user_id=invitations_test_user.id,
                role_type="BWPRi",
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
        # Et une invitation PENDING sur le BW cancelled (idem)
        pending_cancelled_bw = BusinessWall(
            bw_type="media",
            status=BWStatus.CANCELLED.value,
            owner_id=test_inviting_user_with_profile.id,
            payer_id=test_inviting_user_with_profile.id,
            organisation_id=inviting_org.id,
            name="Vestige PENDING BW",
        )
        db_session.add(pending_cancelled_bw)
        db_session.flush()
        db_session.add(
            RoleAssignment(
                business_wall_id=pending_cancelled_bw.id,
                user_id=invitations_test_user.id,
                role_type="BWMi",
                invitation_status=InvitationStatus.PENDING.value,
            )
        )
        db_session.flush()

        view = InvitationsView()
        accepted_bw_names = {
            r["bw_name"] for r in view._accepted_role_invitations(invitations_test_user)
        }
        pending_bw_names = {
            r["bw_name"] for r in view._role_invitations(invitations_test_user)
        }
        assert "Vestige BW cancelled" not in accepted_bw_names
        assert "Vestige PENDING BW" not in pending_bw_names
        # And the active BW still appears
        assert inviting_org.bw_name in accepted_bw_names


class TestInvitationsUserWithAutoOrg:
    """Tests for user with auto-created organization."""

    def test_invitations_shows_auto_org(
        self,
        db_session: Session,
        invitations_test_user: User,
        app: Flask,
    ):
        """Test invitations page shows auto organization."""

        client = make_authenticated_client(app, invitations_test_user)
        response = client.get("/preferences/invitations")
        assert response.status_code == 200
