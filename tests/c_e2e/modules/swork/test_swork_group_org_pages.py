# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork group and organisation views."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow
import pytest
from flask import Flask, g

from app.models.auth import KYCProfile, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.events.models import EventPost
from app.modules.swork.models import Group
from app.modules.swork.views._common import (
    GROUP_TABS,
    is_group_member,
    join_group,
    leave_group,
)
from app.modules.swork.views.group import GroupVM
from app.modules.swork.views.organisation import (
    TAB_CLASSES,
    OrgContactsTab,
    OrgEventsTab,
    OrgPressBookTab,
    OrgPressReleasesTab,
    OrgProfileTab,
    OrgPublicationsTab,
    OrgVM,
)
from app.modules.wire.models import (
    ArticlePost,
    ArticlePurchase,
    PressReleasePost,
    PurchaseProduct,
    PurchaseStatus,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user_with_profile(db_session: Session) -> User:
    """Create a test user with profile for swork tests."""
    user = User(email="swork_grp_test@example.com")
    user.first_name = "Test"
    user.last_name = "User"
    user.photo = b""

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def second_user_with_profile(db_session: Session) -> User:
    """Create a second test user."""
    user = User(email="swork_grp_test2@example.com")
    user.first_name = "Second"
    user.last_name = "Person"
    user.photo = b""

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_group(db_session: Session, test_user_with_profile: User) -> Group:
    """Create a test group."""
    group = Group(
        name="Test Group",
        owner_id=test_user_with_profile.id,
        privacy="public",
    )
    db_session.add(group)
    db_session.flush()
    return group


@pytest.fixture
def test_organisation(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Organisation")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_organisation_media(
    db_session: Session, test_user_with_profile: User
) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Organisation")
    db_session.add(org)
    db_session.flush()

    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=test_user_with_profile.id,
        payer_id=test_user_with_profile.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Link organisation to BW
    org.bw_id = bw.id
    org.bw_active = bw.bw_type
    db_session.flush()

    return org


@pytest.fixture
def auto_organisation(db_session: Session) -> Organisation:
    """Create an auto (no bw_id) organisation."""
    org = Organisation(name="Auto Organisation")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user_with_profile: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user_with_profile.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(test_user_with_profile.fs_uniquifier)
            if hasattr(test_user_with_profile, "fs_uniquifier")
            else str(test_user_with_profile.id)
        )

    return client


# =============================================================================
# Group Tests
# =============================================================================


class TestGroupTabs:
    """Test GROUP_TABS configuration."""

    def test_tabs_structure(self):
        """Test GROUP_TABS has expected structure."""
        assert isinstance(GROUP_TABS, list)
        assert len(GROUP_TABS) == 3

        tab_ids = [t["id"] for t in GROUP_TABS]
        assert "wall" in tab_ids
        assert "description" in tab_ids
        assert "members" in tab_ids

    def test_tabs_have_labels(self):
        """Test all tabs have labels."""
        for tab in GROUP_TABS:
            assert "id" in tab
            assert "label" in tab


class TestGroupEndpoint:
    """Test group HTTP endpoints."""

    def test_group_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session, test_group: Group
    ):
        """Test group page is accessible."""
        response = authenticated_client.get(f"/swork/groups/{test_group.id}")
        assert response.status_code in (200, 302)

    def test_toggle_join_via_post(
        self, authenticated_client: FlaskClient, db_session: Session, test_group: Group
    ):
        """Test toggle-join action via POST."""
        response = authenticated_client.post(
            f"/swork/groups/{test_group.id}",
            data={"action": "toggle-join"},
        )
        assert response.status_code in (200, 302)


class TestGroupVM:
    """Test GroupVM view model."""

    def test_group_property(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test group property returns the group."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = GroupVM(test_group)
            assert vm.group == test_group

    def test_extra_attrs_returns_dict(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test extra_attrs returns expected dictionary."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = GroupVM(test_group)
            attrs = vm.extra_attrs()

            assert isinstance(attrs, dict)
            assert "members" in attrs
            assert "is_member" in attrs
            assert "timeline" in attrs
            assert "cover_image_url" in attrs
            assert "logo_url" in attrs

    def test_get_members_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test get_members returns list of users."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = GroupVM(test_group)
            members = vm.get_members()

            assert isinstance(members, list)


class TestGroupMembershipFunctions:
    """Test group membership functions."""

    def test_is_group_member_returns_false_for_non_member(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test is_group_member returns False for non-member."""
        with app.test_request_context():
            g.user = test_user_with_profile
            result = is_group_member(test_user_with_profile, test_group)
            assert result is False


class TestGroupJoinLeave:
    """Test group join/leave functionality."""

    def test_join_adds_user_to_group(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test join_group() adds user to group membership table."""
        with app.test_request_context():
            g.user = test_user_with_profile

            # Verify not a member initially
            assert is_group_member(test_user_with_profile, test_group) is False

            # Mock post_activity at source module to avoid ActivityType assertion
            with patch("app.services.activity_stream.post_activity"):
                join_group(test_user_with_profile, test_group)

            # Verify now a member
            assert is_group_member(test_user_with_profile, test_group) is True

    def test_leave_removes_user_from_group(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test leave_group() removes user from group membership table."""
        with app.test_request_context():
            g.user = test_user_with_profile

            # First add user to group
            with patch("app.services.activity_stream.post_activity"):
                join_group(test_user_with_profile, test_group)

            # Verify is a member
            assert is_group_member(test_user_with_profile, test_group) is True

            # Now leave the group
            with patch("app.services.activity_stream.post_activity"):
                leave_group(test_user_with_profile, test_group)

            # Verify no longer a member
            assert is_group_member(test_user_with_profile, test_group) is False

    def test_is_group_member_returns_true_after_join(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test is_group_member returns True after joining."""
        with app.test_request_context():
            g.user = test_user_with_profile

            with patch("app.services.activity_stream.post_activity"):
                join_group(test_user_with_profile, test_group)

            result = is_group_member(test_user_with_profile, test_group)
            assert result is True


# =============================================================================
# Organisation Tests
# =============================================================================


class TestOrgEndpoint:
    """Test organisation HTTP endpoints."""

    def test_org_page_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_organisation: Organisation,
    ):
        """Test organisation page is accessible."""
        response = authenticated_client.get(
            f"/swork/organisations/{test_organisation.id}"
        )
        assert response.status_code in (200, 302)


# =============================================================================
# Tab Classes Tests
# =============================================================================


class TestTabClasses:
    """Test TAB_CLASSES configuration."""

    def test_tab_classes_count(self):
        """Test TAB_CLASSES has expected number of tabs."""
        assert len(TAB_CLASSES) == 6

    def test_tab_classes_types(self):
        """Test TAB_CLASSES contains expected tab types."""
        tab_types = [cls.__name__ for cls in TAB_CLASSES]
        assert "OrgProfileTab" in tab_types
        assert "OrgContactsTab" in tab_types
        assert "OrgPublicationsTab" in tab_types
        assert "OrgPressBookTab" in tab_types
        assert "OrgPressReleasesTab" in tab_types
        assert "OrgEventsTab" in tab_types


class TestOrgProfileTab:
    """Test OrgProfileTab class."""

    def test_tab_id(self):
        """Test OrgProfileTab has correct id."""
        assert OrgProfileTab.id == "profile"

    def test_tab_label(self):
        """Test OrgProfileTab has correct label."""
        assert OrgProfileTab.label == "A propos"

    def test_guard_always_true(self, test_organisation: Organisation):
        """Test guard always returns True."""
        tab = OrgProfileTab(org=test_organisation)
        assert tab.guard() is True


class TestOrgContactsTab:
    """Test OrgContactsTab class."""

    def test_tab_id(self):
        """Test OrgContactsTab has correct id."""
        assert OrgContactsTab.id == "contacts"

    def test_label_includes_count(
        self, app: Flask, db_session: Session, test_organisation: Organisation
    ):
        """Test label includes member count."""
        with app.test_request_context():
            tab = OrgContactsTab(org=test_organisation)
            label = tab.label

            assert "Contacts" in label
            assert "(" in label
            assert ")" in label

    def test_guard_returns_true(self, test_organisation: Organisation):
        """Test guard returns True."""
        tab = OrgContactsTab(org=test_organisation)
        assert tab.guard() is True


class TestOrgPublicationsTab:
    """Test OrgPublicationsTab class."""

    def test_tab_id(self):
        """Test OrgPublicationsTab has correct id."""
        assert OrgPublicationsTab.id == "publications"

    def test_guard_true_for_media_bw(
        self,
        app: Flask,
        db_session: Session,
        test_organisation_media: Organisation,
    ):
        """Test guard returns True for organisation with MEDIA BusinessWall."""

        tab = OrgPublicationsTab(org=test_organisation_media)
        assert tab.guard() is True

    def test_guard_true_for_corporate_media_bw(
        self,
        app: Flask,
        db_session: Session,
        test_organisation: Organisation,
        test_user_with_profile: User,
    ):
        """Test guard returns True for organisation with CORPORATE_MEDIA BusinessWall."""
        # Create an active BusinessWall with corporate_media type
        bw = BusinessWall(
            bw_type="corporate_media",
            status=BWStatus.ACTIVE.value,
            owner_id=test_user_with_profile.id,
            payer_id=test_user_with_profile.id,
            organisation_id=test_organisation.id,
        )
        db_session.add(bw)
        db_session.flush()

        # Link organisation to BW
        test_organisation.bw_id = bw.id
        test_organisation.bw_active = bw.bw_type
        db_session.flush()

        tab = OrgPublicationsTab(org=test_organisation)
        assert tab.guard() is True

    def test_guard_false_for_no_bw(self, test_organisation: Organisation):
        """Test guard returns False for organisation without BusinessWall."""
        tab = OrgPublicationsTab(org=test_organisation)
        assert tab.guard() is False


class TestOrgPressBookTab:
    """Test OrgPressBookTab class."""

    def test_tab_id(self):
        """Test OrgPressBookTab has correct id."""
        assert OrgPressBookTab.id == "press-book"

    def test_guard_false_for_auto(self, auto_organisation: Organisation):
        """Test guard returns False for AUTO organisation."""
        tab = OrgPressBookTab(org=auto_organisation)
        assert tab.guard() is False

    def test_guard_true_for_non_auto(self, test_organisation_media: Organisation):
        """Test guard returns True for non-AUTO organisation."""
        tab = OrgPressBookTab(org=test_organisation_media)
        assert tab.guard() is True

    def test_label_dynamic_count_zero(
        self,
        app: Flask,
        db_session: Session,
        test_organisation_media: Organisation,
    ):
        """Regression for bug 0125-A: label was hardcoded "Press Book (0)".

        With no press releases, count must still resolve dynamically (and
        equal 0), not be a static string.
        """
        with app.test_request_context():
            tab = OrgPressBookTab(org=test_organisation_media)
            assert tab.label == "Press Book (0)"

    def test_label_is_zero_until_justificatif_implemented(
        self,
        app: Flask,
        db_session: Session,
        test_organisation_media: Organisation,
        test_user_with_profile: User,
    ):
        """Bug #0180 (Erick, 2026-06-02) : « le compteur affiche 4 mais
        si l'on cliqu, il n'y a aucun contenu. Normal, ces contenus ne
        peuvent provenir que du Justificatif de publication qui n'est
        pas encore installé. → Suggestion : mettre le compteur à zéro
        et le mettre en accord avec le nombre de contenus lorsque le
        mécanisme du Justificatif de publication sera effectif. »

        Press Book ≠ Communiqués : Press Book lists Justificatifs (an
        unimplemented module), Communiqués lists press releases.
        Counter must stay at 0 even when public press releases exist
        for the org — they belong to the Communiqués tab.
        """
        for i in range(3):
            post = PressReleasePost()
            post.title = f"Public PR {i}"
            post.owner_id = test_user_with_profile.id
            post.publisher_id = test_organisation_media.id
            post.status = PublicationStatus.PUBLIC  # type: ignore[assignment]
            db_session.add(post)
        db_session.flush()

        with app.test_request_context():
            tab = OrgPressBookTab(org=test_organisation_media)
            assert tab.label == "Press Book (0)"

    def test_label_reflects_paid_justificatif_count(
        self,
        app: Flask,
        db_session: Session,
        test_organisation_media: Organisation,
        test_user_with_profile: User,
    ):
        """Ticket #0195 — the counter is now wired to
        `count_org_press_book` and reflects the number of distinct
        articles for which any member of the org owns a PAID
        JUSTIFICATIF purchase."""
        # Put `test_user_with_profile` at the media org so their PAID
        # justificatifs aggregate into the org's Press Book.
        test_user_with_profile.organisation = test_organisation_media
        test_user_with_profile.organisation_id = test_organisation_media.id
        db_session.flush()

        for i in range(2):
            post = ArticlePost(
                title=f"Justified article {i}",
                owner_id=test_user_with_profile.id,
                status=PublicationStatus.PUBLIC,
            )
            db_session.add(post)
            db_session.flush()
            db_session.add(
                ArticlePurchase(
                    post_id=post.id,
                    owner_id=test_user_with_profile.id,
                    product_type=PurchaseProduct.JUSTIFICATIF,
                    status=PurchaseStatus.PAID,
                    amount_cents=100,
                    paid_at=datetime.now(UTC),
                )
            )
        db_session.flush()

        with app.test_request_context():
            tab = OrgPressBookTab(org=test_organisation_media)
            assert tab.label == "Press Book (2)"


class TestOrgPressReleasesTab:
    """Test OrgPressReleasesTab class."""

    def test_tab_id(self):
        """Test OrgPressReleasesTab has correct id."""
        assert OrgPressReleasesTab.id == "press-releases"

    def test_guard_false_for_auto(self, auto_organisation: Organisation):
        """Test guard returns False for AUTO organisation."""
        tab = OrgPressReleasesTab(org=auto_organisation)
        assert tab.guard() is False

    def test_guard_true_for_non_auto(self, test_organisation_media: Organisation):
        """Test guard returns True for non-AUTO organisation."""
        tab = OrgPressReleasesTab(org=test_organisation_media)
        assert tab.guard() is True


class TestOrgEventsTab:
    """Test OrgEventsTab class."""

    def test_tab_id(self):
        """Test OrgEventsTab has correct id."""
        assert OrgEventsTab.id == "events"

    def test_guard_false_for_auto(self, auto_organisation: Organisation):
        """Test guard returns False for AUTO organisation."""
        tab = OrgEventsTab(org=auto_organisation)
        assert tab.guard() is False

    def test_guard_true_for_non_auto(self, test_organisation_media: Organisation):
        """Test guard returns True for non-AUTO organisation."""
        tab = OrgEventsTab(org=test_organisation_media)
        assert tab.guard() is True

    def test_label_counts_direct_publisher(
        self,
        app: Flask,
        db_session: Session,
        test_organisation_media: Organisation,
        test_user_with_profile: User,
    ):
        """Events directly attributed to the org increment the label."""
        now = arrow.now()
        event = EventPost(
            title="Direct Event",
            owner_id=test_user_with_profile.id,
            publisher_id=test_organisation_media.id,
            status=PublicationStatus.PUBLIC,
            start_datetime=now,
            end_datetime=now.shift(days=1),
            genre="Salon",
            sector="Tech",
        )
        db_session.add(event)
        db_session.flush()

        with app.test_request_context():
            tab = OrgEventsTab(org=test_organisation_media)
            assert tab.label == "Evénements (1)"

    def test_label_counts_event_published_on_behalf_by_agency_member(
        self,
        app: Flask,
        db_session: Session,
        test_organisation_media: Organisation,
        test_user_with_profile: User,
    ):
        """#0135 — When an agency member publishes an event for a client
        (publisher_id=client), the event must also surface on the agency
        BW's « Événements » tab, via the owner.organisation clause.
        Mirrors the press-release semantics (#0125).
        """
        test_user_with_profile.organisation = test_organisation_media
        test_user_with_profile.organisation_id = test_organisation_media.id
        client_org = Organisation(name="Client Org for Events")
        db_session.add(client_org)
        db_session.flush()

        now = arrow.now()
        event = EventPost(
            title="Delegated Event",
            owner_id=test_user_with_profile.id,
            publisher_id=client_org.id,
            status=PublicationStatus.PUBLIC,
            start_datetime=now,
            end_datetime=now.shift(days=1),
            genre="Salon",
            sector="Logistique",
        )
        db_session.add(event)
        db_session.flush()

        with app.test_request_context():
            agency_tab = OrgEventsTab(org=test_organisation_media)
            client_tab = OrgEventsTab(org=client_org)
            assert agency_tab.label == "Evénements (1)", (
                "delegated event must count on the agency BW (#0135)"
            )
            assert client_tab.label == "Evénements (1)"

    def test_label_excludes_drafts(
        self,
        app: Flask,
        db_session: Session,
        test_organisation_media: Organisation,
        test_user_with_profile: User,
    ):
        """Draft events must not appear in the count."""
        now = arrow.now()
        event = EventPost(
            title="Draft Event",
            owner_id=test_user_with_profile.id,
            publisher_id=test_organisation_media.id,
            status=PublicationStatus.DRAFT,
            start_datetime=now,
            end_datetime=now.shift(days=1),
            genre="Salon",
            sector="Tech",
        )
        db_session.add(event)
        db_session.flush()

        with app.test_request_context():
            tab = OrgEventsTab(org=test_organisation_media)
            assert tab.label == "Evénements (0)"

    def test_events_tab_template_does_not_double_wrap_li(self):
        """Bug #0179 (Erick, 2026-06-02) : « les événements publiés
        sont uniquement sur la colonne de droite tandis que la colonne
        de gauche est vide. Cela donne une impression bizarre. »

        Root cause : the `event-card` component already wraps itself in
        `<li class="card shadow ...">`. The tab template was wrapping
        each component call in *another* `<li class="bg-white rounded
        shadow">`, creating nested `<li>` inside the `<ul
        grid-cols-2>`. Browsers fall back to a single-column layout
        when grid items are nested lists. The fix is to drop the
        outer wrapper and let the event-card's own `<li>` be the
        direct grid child.
        """
        template_path = (
            Path(__file__).resolve().parents[4]
            / "src/app/modules/swork/templates/pages/org/org--tab-events.html"
        )
        source = template_path.read_text()
        # The bug is the redundant outer wrapper around the component
        # call. The string is removed by the fix; if a future refactor
        # re-introduces it, this test catches the regression.
        assert '<li class="bg-white rounded shadow">' not in source, (
            "events tab must not wrap event-card components in an extra <li>; "
            "the event_card.j2 component already opens with <li>, double "
            "nesting breaks the grid-cols-2 layout (#0179)"
        )


# =============================================================================
# OrgVM Tests
# =============================================================================


class TestOrgVM:
    """Test OrgVM from views/organisation.py."""

    def test_org_property(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test org property returns the organisation."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgVM(test_organisation)
            assert vm.org == test_organisation

    def test_extra_attrs_returns_dict(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test extra_attrs returns expected dictionary."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgVM(test_organisation)
            attrs = vm.extra_attrs()

            assert isinstance(attrs, dict)
            assert "members" in attrs
            assert "logo_url" in attrs
            assert "cover_image_url" in attrs
            assert "press_releases" in attrs
            assert "publications" in attrs
            assert "is_following" in attrs
            assert "timeline" in attrs

    def test_get_members_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_members returns list of users."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgVM(test_organisation)
            members = vm.get_members()

            assert isinstance(members, list)

    def test_get_logo_url_for_auto(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        auto_organisation: Organisation,
    ):
        """Test get_logo_url for AUTO organisation."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgVM(auto_organisation)
            url = vm.get_logo_url()

            assert url == "/static/img/logo-page-non-officielle.png"

    def test_get_cover_image_url_for_auto(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        auto_organisation: Organisation,
    ):
        """Test get_cover_image_url for inactive (auto) organisation."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgVM(auto_organisation)
            url = vm.get_cover_image_url()

            assert url == "/static/img/transparent-square.png"

    def test_get_press_releases_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_press_releases returns list."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgVM(test_organisation)
            releases = vm.get_press_releases()

            assert isinstance(releases, list)

    def test_get_publications_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_publications returns list."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgVM(test_organisation)
            publications = vm.get_publications()

            assert isinstance(publications, list)

    def test_get_events_includes_delegated_events_on_agency_bw(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation_media: Organisation,
    ):
        """#0135 — Igor (PR agency member) publishes an event for his
        client Fake-Davi Logistique. On Erick's 2026-05-22 reread, the
        event was visible on the client BW but not on the agency BW.
        Now get_events() must surface it on both, via the same dual-case
        clause used for press releases.
        """
        test_user_with_profile.organisation = test_organisation_media
        test_user_with_profile.organisation_id = test_organisation_media.id
        client_org = Organisation(name="Fake-Davi Logistique")
        db_session.add(client_org)
        db_session.flush()

        now = arrow.now()
        event = EventPost(
            title="L'Orange bleue fête ses 30 ans",
            owner_id=test_user_with_profile.id,
            publisher_id=client_org.id,
            status=PublicationStatus.PUBLIC,
            start_datetime=now,
            end_datetime=now.shift(days=1),
            genre="Salon",
            sector="Logistique",
        )
        db_session.add(event)
        db_session.flush()

        with app.test_request_context():
            g.user = test_user_with_profile

            agency_events = OrgVM(test_organisation_media).get_events()
            assert len(agency_events) == 1, (
                "delegated event must appear on the agency BW Events tab "
                "(#0135) — was previously missing because get_events() "
                "only matched publisher_id"
            )
            assert agency_events[0].title == event.title

            client_events = OrgVM(client_org).get_events()
            assert len(client_events) == 1, (
                "delegated event must also still appear on the client BW"
            )

    def test_get_events_excludes_drafts(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation_media: Organisation,
    ):
        """Draft events must not leak into the public Events tab."""
        now = arrow.now()
        event = EventPost(
            title="Draft Only",
            owner_id=test_user_with_profile.id,
            publisher_id=test_organisation_media.id,
            status=PublicationStatus.DRAFT,
            start_datetime=now,
            end_datetime=now.shift(days=1),
            genre="Salon",
            sector="Tech",
        )
        db_session.add(event)
        db_session.flush()

        with app.test_request_context():
            g.user = test_user_with_profile
            events = OrgVM(test_organisation_media).get_events()
            assert events == []
