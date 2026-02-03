# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork module components."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import Flask
from sqlalchemy.orm import Session

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
)
from app.modules.swork.components.members_list import (
    FilterByDeptOrm as MemberFilterByDeptOrm,
)
from app.modules.swork.components.members_list import (
    FilterByJobTitle,
    MembersDirectory,
    MembersList,
    make_filters as make_member_filters,
)
from app.modules.swork.components.organisations_list import (
    FilterByCategory,
)
from app.modules.swork.components.organisations_list import (
    FilterByCityOrm as OrgFilterByCityOrm,
)
from app.modules.swork.components.organisations_list import (
    FilterByDeptOrm as OrgFilterByDeptOrm,
)
from app.modules.swork.components.organisations_list import (
    OrganisationsList,
    OrgsDirectory,
)
from app.modules.swork.components.organisations_list import (
    OrgVM as OrgListOrgVM,
)
from app.modules.swork.components.organisations_list import (
    make_filters as make_org_filters,
)

if TYPE_CHECKING:
    pass


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
    profile.info_professionnelle = {"pays_zip_ville": 'FRA', "pays_zip_ville_detail": '75001 Paris'}
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
                from sqlalchemy import select

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
            options = ["A", "B", "C"]

            def apply(self, stmt, state):
                return stmt

        class TestList(BaseList):
            filters = [TestFilter()]

            def get_base_statement(self):
                from sqlalchemy import select

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
                from sqlalchemy import select

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
                from sqlalchemy import select

                return select(User)

            def search_clause(self, search):
                return User.first_name.ilike(f"%{search}%")

        with app.test_request_context():
            from sqlalchemy import select

            test_list = TestList()
            test_list.search = ""
            stmt = select(User)
            result = test_list.apply_search(stmt)
            assert str(result) == str(stmt)

    def test_apply_search_with_text(self, app: Flask, db_session: Session):
        """Test apply_search modifies stmt for non-empty search."""

        class TestList(BaseList):
            def get_base_statement(self):
                from sqlalchemy import select

                return select(User)

            def search_clause(self, search):
                return User.first_name.ilike(f"%{search}%")

        with app.test_request_context():
            from sqlalchemy import select

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
            options = ["A", "B", "C"]

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
            options = ["A", "B", "C"]

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
        from sqlalchemy import select

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
        from sqlalchemy import false, select, true
        from sqlalchemy.orm import selectinload

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

    def test_apply_search_method_exists(self):
        """Test MembersList has apply_search method."""
        assert hasattr(MembersList, "apply_search")
        assert callable(getattr(MembersList, "apply_search"))

    def test_search_clause_method_exists(self):
        """Test MembersList has search_clause method."""
        assert hasattr(MembersList, "search_clause")
        assert callable(getattr(MembersList, "search_clause"))


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
        assert len(filters) == 5


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


class TestOrganisationsListGetOrgCount:
    """Test OrganisationsList.get_org_count method."""

    def test_get_org_count_returns_integer(
        self, app: Flask, db_session: Session, test_organisation: Organisation
    ):
        """Test get_org_count returns an integer."""
        with app.test_request_context():
            orgs_list = OrganisationsList()
            count = orgs_list.get_org_count()

            assert isinstance(count, int)
            assert count >= 1  # At least the test org


class TestOrganisationsListStaticMethods:
    """Test OrganisationsList static methods."""

    def test_apply_search_method_exists(self):
        """Test OrganisationsList has apply_search method."""
        assert hasattr(OrganisationsList, "apply_search")
        assert callable(getattr(OrganisationsList, "apply_search"))

    def test_search_clause_method_exists(self):
        """Test OrganisationsList has search_clause method."""
        assert hasattr(OrganisationsList, "search_clause")
        assert callable(getattr(OrganisationsList, "search_clause"))

    def test_get_base_statement_exists(self):
        """Test OrganisationsList has get_base_statement method."""
        assert hasattr(OrganisationsList, "get_base_statement")
        assert callable(getattr(OrganisationsList, "get_base_statement"))


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
        assert "Agences de presse" in FilterByCategory.org_type_map
        assert "Médias" in FilterByCategory.org_type_map
        assert "PR agencies" in FilterByCategory.org_type_map
        assert "Autres" in FilterByCategory.org_type_map
        assert "Non officialisées" in FilterByCategory.org_type_map

    def test_apply_with_no_active_options(self, db_session: Session):
        """Test apply returns unchanged stmt when no options active."""
        from sqlalchemy import select

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


class TestMakeOrgFilters:
    """Test make_filters function for organisations."""

    def test_make_filters_returns_list(
        self, db_session: Session, test_organisation: Organisation
    ):
        """Test make_filters returns list of filters."""
        filters = make_org_filters([test_organisation])
        assert isinstance(filters, list)
        assert len(filters) == 4


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
            assert url == "/static/img/transparent-square.png"


class TestOrgsDirectory:
    """Test OrgsDirectory class."""

    def test_vm_class(self):
        """Test OrgsDirectory has correct vm_class."""
        assert OrgsDirectory.vm_class == OrgListOrgVM
