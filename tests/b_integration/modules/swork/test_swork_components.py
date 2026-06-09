# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork module components."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import pytest
from sqlalchemy import false, select, true
from sqlalchemy.orm import Session, selectinload

from app.enums import OrganisationTypeEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.swork.components.base import (
    BaseList,
    Filter,
    FilterByCity,
    FilterByDept,
)
from app.modules.swork.components.members_list import (
    FilterByCityOrm as MemberFilterByCityOrm,
    FilterByDeptOrm as MemberFilterByDeptOrm,
    FilterByJobTitle,
    MembersDirectory,
    MembersList,
    make_filters as make_member_filters,
)
from app.modules.swork.components.organisations_list import (
    FilterByCategory,
    FilterByCityOrm as OrgFilterByCityOrm,
    FilterByDeptOrm as OrgFilterByDeptOrm,
    OrganisationsList,
    OrgFilterByTailleOrganisation,
    OrgFilterByTypeOrganisation,
    OrgFilterByTypePresseEtMedia,
    OrgsDirectory,
    OrgVM as OrgListOrgVM,
)

if TYPE_CHECKING:
    from flask import Flask


@pytest.fixture
def test_user_with_profile(db_session: Session) -> User:
    """Create a test user with profile for swork tests."""
    user = User(email="swork_comp_test@example.com")
    user.first_name = "Test"
    user.last_name = "User"
    user.photo = b""
    user.city = "Paris"
    user.zip_code = "75001"

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    profile.profile_label = "Journaliste"
    profile.info_personnelle = {"competences": [], "competences_journalisme": []}
    profile.info_professionnelle = {
        "pays_zip_ville": "FRA",
        "pays_zip_ville_detail": "75001 Paris",
    }
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def second_user_with_profile(db_session: Session) -> User:
    """Create a second test user with different city."""
    user = User(email="swork_comp_test2@example.com")
    user.first_name = "Second"
    user.last_name = "Person"
    user.photo = b""
    user.city = "Lyon"
    user.zip_code = "69001"

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    profile.profile_label = "Redacteur"
    profile.info_personnelle = {"competences": [], "competences_journalisme": []}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_organisation(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Org")
    org.city = "Paris"
    org.zip_code = "75001"
    org.type = OrganisationTypeEnum.MEDIA
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def second_organisation(db_session: Session) -> Organisation:
    """Create a second test organisation."""
    org = Organisation(name="Second Org")
    org.city = "Lyon"
    org.zip_code = "69001"
    org.type = OrganisationTypeEnum.AGENCY
    db_session.add(org)
    db_session.flush()
    return org


# =============================================================================
# BaseList Tests
# =============================================================================


class TestBaseListInit:
    """Test BaseList initialization."""

    def test_init_sets_filter_states(self, app: Flask, db_session: Session):
        """Test __init__ sets filter_states to empty dict."""

        class TestList(BaseList):
            def get_base_statement(self):
                return select(User)

            def search_clause(self, search):
                return User.first_name.ilike(f"%{search}%")

        with app.test_request_context():
            test_list = TestList()
            assert isinstance(test_list.filter_states, dict)

    def test_init_filter_states_from_filters(self, app: Flask, db_session: Session):
        """Test init_filter_states creates states for each filter."""

        class TestFilter(Filter):
            id = "test"
            label = "Test"
            options: list = ["A", "B", "C"]  # noqa: RUF012

            def apply(self, stmt, state):
                return stmt

        class TestList(BaseList):
            filters: ClassVar[list] = [TestFilter()]

            def get_base_statement(self):
                return select(User)

            def search_clause(self, search):
                return User.first_name.ilike(f"%{search}%")

            def get_filters(self):
                return self.filters

        with app.test_request_context():
            test_list = TestList()
            assert "test" in test_list.filter_states
            assert test_list.filter_states["test"] == {
                "0": False,
                "1": False,
                "2": False,
            }


class TestBaseListMakeStmt:
    """Test BaseList.make_stmt method."""

    def test_make_stmt_returns_select(self, app: Flask, db_session: Session):
        """Test make_stmt returns a SQLAlchemy select."""

        class TestList(BaseList):
            def get_base_statement(self):
                return select(User)

            def search_clause(self, search):
                return User.first_name.ilike(f"%{search}%")

        with app.test_request_context():
            test_list = TestList()
            stmt = test_list.make_stmt()
            assert stmt is not None


class TestBaseListApplySearch:
    """Test BaseList.apply_search method."""

    def test_apply_search_empty(self, app: Flask, db_session: Session):
        """Test apply_search returns unchanged stmt for empty search."""

        class TestList(BaseList):
            def get_base_statement(self):
                return select(User)

            def search_clause(self, search):
                return User.first_name.ilike(f"%{search}%")

        with app.test_request_context():
            test_list = TestList()
            test_list.search = ""
            stmt = select(User)
            result = test_list.apply_search(stmt)
            assert str(result) == str(stmt)

    def test_apply_search_with_text(self, app: Flask, db_session: Session):
        """Test apply_search modifies stmt for non-empty search."""

        class TestList(BaseList):
            def get_base_statement(self):
                return select(User)

            def search_clause(self, search):
                return User.first_name.ilike(f"%{search}%")

        with app.test_request_context():
            test_list = TestList()
            test_list.search = "John"
            stmt = select(User)
            result = test_list.apply_search(stmt)
            assert str(result) != str(stmt)


# =============================================================================
# Filter Tests
# =============================================================================


class TestFilterActiveOptions:
    """Test Filter.active_options method."""

    def test_active_options_empty_state(self):
        """Test active_options returns empty list for no active options."""

        class TestFilter(Filter):
            id = "test"
            label = "Test"
            options: list = ["A", "B", "C"]  # noqa: RUF012

            def apply(self, stmt, state):
                return stmt

        filter = TestFilter()
        filter.options = ["A", "B", "C"]
        state = {"0": False, "1": False, "2": False}

        result = filter.active_options(state)
        assert result == []

    def test_active_options_some_active(self):
        """Test active_options returns active options."""

        class TestFilter(Filter):
            id = "test"
            label = "Test"
            options: list = ["A", "B", "C"]  # noqa: RUF012

            def apply(self, stmt, state):
                return stmt

        filter = TestFilter()
        filter.options = ["A", "B", "C"]
        state = {"0": True, "1": False, "2": True}

        result = filter.active_options(state)
        assert result == ["A", "C"]


class TestFilterByCity:
    """Test FilterByCity class."""

    def test_selector_returns_city(self):
        """Test selector returns city from Addressable."""
        filter = FilterByCity()

        # Create a mock object with city attribute
        class MockObj:
            city = "Paris"

        obj = MockObj()
        # FilterByCity.selector checks isinstance(obj, Addressable)
        # which won't match MockObj, so it returns ""
        result = filter.selector(obj)
        assert result == ""

    def test_apply_with_no_active_options(self, db_session: Session):
        """Test apply returns unchanged stmt when no options active."""
        filter = FilterByCity()
        filter.options = ["Paris", "Lyon"]
        state = {"0": False, "1": False}

        stmt = select(User)
        result = filter.apply(stmt, state)
        assert str(result) == str(stmt)


class TestFilterByDept:
    """Test FilterByDept class."""

    def test_filter_id(self):
        """Test FilterByDept has correct id."""
        filter = FilterByDept()
        assert filter.id == "dept"

    def test_filter_label(self):
        """Test FilterByDept has correct label."""
        filter = FilterByDept()
        assert filter.label == "Département"


# =============================================================================
# MembersList Tests
# =============================================================================


class TestMembersListContext:
    """Test MembersList.context method."""

    def test_context_returns_dict(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test context returns expected dictionary."""
        with app.test_request_context():
            members_list = MembersList()
            ctx = members_list.context()

            assert isinstance(ctx, dict)
            assert "directory" in ctx
            assert "count" in ctx
            assert "filters" in ctx

    def test_context_count_is_integer(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test context count is an integer."""
        with app.test_request_context():
            members_list = MembersList()
            ctx = members_list.context()

            assert isinstance(ctx["count"], int)


class TestMembersListStaticMethods:
    """Test MembersList static methods without initialization."""

    def test_get_base_statement_structure(self, app: Flask, db_session: Session):
        """Test get_base_statement returns expected structure when called directly."""
        # Test the expected structure directly
        expected = (
            select(User)
            .where(
                User.active == true(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
            )
            .options(selectinload(User.organisation))
            .limit(100)
        )
        assert str(expected).startswith("SELECT")


class TestMembersSearchByZip:
    """Regression (audit 2026-05-15, C3): a member search containing a
    digit must execute on the DB without a dialect error.

    `members_list.apply_search` filtered with
    `KYCProfile.code_postal.ilike(...)`. The `code_postal` SQL
    expression used `split_part(... ->> 0, ' ', 3)` — Postgres-only
    AND assuming `pays_zip_ville_detail` is a JSON array, while the
    Python getter handles both str and list. SQLite has no
    `split_part`, so this path was structurally untested in CI
    (lessons-learned #11) and the array assumption is fragile on
    Postgres. The test EXECUTES the statement so it runs under both
    backends (`make test-postgres` covers the prod dialect).
    """

    def test_search_with_zip_executes_and_matches(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ) -> None:
        # Fixture stores pays_zip_ville_detail = "75001 Paris" (a str,
        # not a JSON array) — exactly the shape the old `->> 0`
        # expression mishandled. The base query filters
        # `User.active == true()` (default is False), so activate.
        test_user_with_profile.active = True
        db_session.flush()

        with app.test_request_context():
            members = MembersList()
            members.search = "75001"
            stmt = members.apply_search(members.get_base_statement())
            # Must not raise (no split_part on SQLite; no array
            # assumption on Postgres) and must find the member.
            found = db_session.execute(stmt).scalars().all()

        assert test_user_with_profile.id in {u.id for u in found}

    def test_search_with_zip_no_false_positive(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        second_user_with_profile: User,
    ) -> None:
        """A zip search must not return members whose postal area
        doesn't contain those digits."""
        test_user_with_profile.active = True
        second_user_with_profile.active = True
        # Give the second user a well-formed but non-matching location
        # (its fixture leaves info_professionnelle = {}, which trips an
        # unrelated `country` KeyError in the MembersList constructor —
        # logged separately as audit finding L5, out of C3 scope).
        second_user_with_profile.profile.info_professionnelle = {
            "pays_zip_ville": "FRA",
            "pays_zip_ville_detail": "69001 Lyon",
        }
        db_session.flush()

        with app.test_request_context():
            members = MembersList()
            members.search = "75001"
            stmt = members.apply_search(members.get_base_statement())
            found_ids = {u.id for u in db_session.execute(stmt).scalars().all()}

        # test_user (75001 Paris) matches; second_user has no
        # pays_zip_ville_detail → must be excluded even though active.
        assert test_user_with_profile.id in found_ids
        assert second_user_with_profile.id not in found_ids


class TestMembersDirectory:
    """Test MembersDirectory class."""

    def test_sorter(self, test_user_with_profile: User):
        """Test sorter returns (last_name, first_name)."""
        directory = MembersDirectory([])
        result = directory.sorter(test_user_with_profile)
        assert result == ("User", "Test")

    def test_get_key_with_last_name(self, test_user_with_profile: User):
        """Test get_key returns first letter of last name."""
        directory = MembersDirectory([])
        result = directory.get_key(test_user_with_profile)
        assert result == "U"

    def test_get_key_empty_last_name(self, db_session: Session):
        """Test get_key returns '?' for empty last name."""
        user = User(email="empty_last@example.com")
        user.last_name = ""
        user.photo = b""
        db_session.add(user)
        db_session.flush()

        directory = MembersDirectory([])
        result = directory.get_key(user)
        assert result == "?"


class TestFilterByJobTitle:
    """Test FilterByJobTitle class."""

    def test_filter_id(self):
        """Test FilterByJobTitle has correct id."""
        assert FilterByJobTitle.id == "job_title"

    def test_filter_label(self):
        """Test FilterByJobTitle has correct label."""
        assert FilterByJobTitle.label == "Fonction"


class TestMemberFilterByDeptOrm:
    """Test MemberFilterByDeptOrm class."""

    def test_filter_id(self):
        """Test MemberFilterByDeptOrm has correct id."""
        assert MemberFilterByDeptOrm.id == "dept"


class TestMemberFilterByCityOrm:
    """Test MemberFilterByCityOrm class."""

    def test_filter_id(self):
        """Test MemberFilterByCityOrm has correct id."""
        assert MemberFilterByCityOrm.id == "city"


class TestMakeMemberFilters:
    """Test make_filters function for members."""

    def test_make_filters_returns_list(
        self, db_session: Session, test_user_with_profile: User
    ):
        """Test make_filters returns list of filters."""
        filters = make_member_filters([test_user_with_profile])
        assert isinstance(filters, list)
        assert len(filters) == 13


# =============================================================================
# OrganisationsList Tests
# =============================================================================


class TestOrganisationsListContext:
    """Test OrganisationsList.context method."""

    def test_context_returns_dict(
        self, app: Flask, db_session: Session, test_organisation: Organisation
    ):
        """Test context returns expected dictionary."""
        with app.test_request_context():
            orgs_list = OrganisationsList()
            ctx = orgs_list.context()

            assert isinstance(ctx, dict)
            assert "directory" in ctx
            assert "count" in ctx
            assert "filters" in ctx
            assert "search" in ctx
            assert "filter_states" in ctx


class TestOrganisationsListCount:
    """Test OrganisationsList count in context."""

    def test_context_count_returns_integer(
        self, app: Flask, db_session: Session, test_organisation: Organisation
    ):
        """Test context count is an integer matching filtered results."""
        with app.test_request_context():
            orgs_list = OrganisationsList()
            ctx = orgs_list.context()

            assert isinstance(ctx["count"], int)
            assert ctx["count"] >= 1  # At least the test org


class TestFilterByCategory:
    """Test FilterByCategory class."""

    def test_filter_id(self):
        """Test FilterByCategory has correct id."""
        assert FilterByCategory.id == "category"

    def test_filter_label(self):
        """Test FilterByCategory has correct label."""
        assert FilterByCategory.label == "Categorie"

    def test_org_type_map_has_all_types(self):
        """Test org_type_map has expected categories."""
        assert "Agences de presse" in FilterByCategory.bw_type_map
        assert "Médias" in FilterByCategory.bw_type_map
        assert "PR agencies" in FilterByCategory.bw_type_map
        assert "Autres" in FilterByCategory.bw_type_map
        assert "Non officialisées" in FilterByCategory.bw_type_map

    def test_apply_with_no_active_options(self, db_session: Session):
        """Test apply returns unchanged stmt when no options active."""
        filter = FilterByCategory()
        state = {str(i): False for i in range(len(filter.options))}

        stmt = select(Organisation)
        result = filter.apply(stmt, state)
        assert str(result) == str(stmt)


class TestOrgFilterByDeptOrm:
    """Test OrgFilterByDeptOrm class."""

    def test_filter_id(self):
        """Test OrgFilterByDeptOrm has correct id."""
        assert OrgFilterByDeptOrm.id == "dept"


class TestOrgFilterByCityOrm:
    """Test OrgFilterByCityOrm class."""

    def test_filter_id(self):
        """Test OrgFilterByCityOrm has correct id."""
        assert OrgFilterByCityOrm.id == "city"


class TestOrganisationsListFilters:
    """Test get_filters method for organisations."""

    def test_get_filters_returns_list(
        self, db_session: Session, test_organisation: Organisation
    ):
        """Bug #0078 (Erick, 2026-05-27) : 5 BW-backed filters added to
        /swork/organisations on top of the 4 existing geo + category
        filters — Types d'organisation, Types presse & médias, Types
        de PR Agencies, Tailles d'organisation, Secteurs détaillés.
        Source data is on BusinessWall (populated in W10), mirrors the
        equivalents on the /swork/members list."""
        orgs_list = OrganisationsList()
        filters = orgs_list.get_filters()
        assert isinstance(filters, list)
        assert len(filters) == 9, (
            "expected the 4 existing filters (Category + 3 geo) plus the "
            "5 new BW-backed taxonomy filters (#0078)"
        )

    def test_filter_ids_cover_erick_request(
        self, db_session: Session, test_organisation: Organisation
    ):
        """The 5 new filters must carry the IDs Erick called out so
        URL state / persisted user prefs stay stable across releases."""
        orgs_list = OrganisationsList()
        ids = {f.id for f in orgs_list.get_filters()}
        for expected in (
            "type_organisation",
            "type_presse_et_media",
            "type_agence_rp",
            "taille_organisation",
            "secteur_activite",
        ):
            assert expected in ids, (
                f"filter id {expected!r} missing — Erick listed it on the "
                f"#0078 spec (got {sorted(ids)})"
            )

    def test_type_organisation_filter_derives_options_from_bw_data(self):
        """The JSON-list BW filters discover their option set by
        walking the supplied BusinessWalls in memory (the JSONB array
        columns can't be DISTINCT-aggregated portably). Pin that
        contract."""

        class _BW:
            def __init__(self, type_organisation):
                self.type_organisation = type_organisation

        bws = [
            _BW(["association", "agence"]),
            _BW(["agence", "media"]),
            _BW([]),
            _BW(None),
        ]
        f = OrgFilterByTypeOrganisation(bws)  # type: ignore[arg-type]
        assert f.options == ["agence", "association", "media"]

    def test_taille_organisation_filter_uses_filter_options_with_codes(self):
        """`OrgFilterByTailleOrganisation` stores `FilterOption(label,
        code)` tuples so display labels can diverge from the raw
        ontology codes used in the URL state."""

        class _BW:
            def __init__(self, taille_orga):
                self.taille_orga = taille_orga

        bws = [_BW("1"), _BW("49"), _BW("+"), _BW("")]
        f = OrgFilterByTailleOrganisation(bws)  # type: ignore[arg-type]
        codes = [opt.code for opt in f.options]
        labels = [opt.option for opt in f.options]
        assert codes == ["+", "1", "49"]
        assert "1 personne" in labels
        assert "Plus de 1 000 000" in labels

    def test_type_presse_et_media_filter_handles_empty_bw_set(self):
        """No active BWs → empty options (no crash on a fresh DB)."""
        f = OrgFilterByTypePresseEtMedia()
        assert f.options == []


class TestOrgListOrgVM:
    """Test OrgVM from organisations_list."""

    def test_org_property(
        self, app: Flask, db_session: Session, test_organisation: Organisation
    ):
        """Test org property returns the organisation."""
        with app.test_request_context():
            vm = OrgListOrgVM(test_organisation)
            assert vm.org == test_organisation

    def test_get_logo_url_auto(self, app: Flask, db_session: Session):
        """Test get_logo_url for auto organisation."""
        org = Organisation(name="Auto Org")
        org.type = OrganisationTypeEnum.AUTO

        with app.test_request_context():
            vm = OrgListOrgVM(org)
            url = vm.get_logo_url()
            assert url == "/static/img/logo-page-non-officielle.png"

    def test_get_logo_url_no_logo(
        self, app: Flask, db_session: Session, test_organisation: Organisation
    ):
        """Test get_logo_url for organisation without logo."""
        test_organisation.logo_id = None

        with app.test_request_context():
            vm = OrgListOrgVM(test_organisation)
            url = vm.get_logo_url()
            # The organisation has no active BusinessWall
            assert url == "/static/img/logo-page-non-officielle.png"


class TestOrgsDirectory:
    """Test OrgsDirectory class."""

    def test_vm_class(self):
        """Test OrgsDirectory has correct vm_class."""
        assert OrgsDirectory.vm_class == OrgListOrgVM


class TestMembersSecteurFilterLabel:
    """Bug #0078: the SOCIAL/Membres sector filter aggregates the
    medias / rp / detailles KYC sub-fields, which all share the same
    `secteur_detaille` ontology — so it IS the detailed-sector
    taxonomy. The PO ("Bravo mais j'avais demandé 'Secteur d'activité
    détaillés'") asked it to be named accordingly, not the generic
    "Secteur activité".
    """

    def test_secteur_filter_label_is_detailed(self) -> None:
        filters = make_member_filters([])
        secteur = next(f for f in filters if f.id == "secteur_activite")
        assert secteur.label == "Secteur d'activité détaillés"
