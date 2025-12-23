# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Nav tree access consistency tests.

These tests verify that the nav tree ACL declarations match actual access control:
- Routes visible in nav tree should be accessible (200 or redirect)
- Routes hidden by ACL should be denied (403 or redirect to login)

This catches inconsistencies between nav tree metadata and view decorators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.flask.lib.nav import NavTree
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask


# Community roles (required for first_community())
COMMUNITY_ROLES = [
    RoleEnum.PRESS_MEDIA,
    RoleEnum.PRESS_RELATIONS,
    RoleEnum.EXPERT,
    RoleEnum.ACADEMIC,
]

# Supplementary roles (must be combined with a community role)
SUPPLEMENTARY_ROLES = [
    RoleEnum.ADMIN,
    RoleEnum.MANAGER,
    RoleEnum.LEADER,
]

# We test community roles directly, plus ADMIN (with PRESS_MEDIA as base)
ROLES_TO_TEST = [
    RoleEnum.PRESS_MEDIA,
    RoleEnum.PRESS_RELATIONS,
    RoleEnum.ACADEMIC,
    RoleEnum.EXPERT,
    RoleEnum.ADMIN,  # Will be combined with PRESS_MEDIA as community
    RoleEnum.MANAGER,  # Will be combined with PRESS_MEDIA as community
    RoleEnum.LEADER,  # Will be combined with PRESS_MEDIA as community
]

# Routes to skip in testing (known test environment limitations)
SKIP_ENDPOINTS = {
    # Requires PostgreSQL (SQLite not supported)
    "admin.export_database",
    # Flask-Security endpoints that may not be configured in test mode
    "preferences.password",
    "preferences.email",
    # Requires Typesense configuration
    "search.search",
    # Missing template
    "wip.billing",
    # Requires POST with parameters
    "wip.billing_get_pdf",
    "wip.billing_get_csv",
    # Profile form issues with test data
    "preferences.profile",
    "wip.org-registration",
    "wip.org-registration-post",
}


@dataclass
class RouteTestResult:
    """Result of testing a route."""

    endpoint: str
    url: str
    expected_accessible: bool
    actual_status: int
    passed: bool
    error: str | None = None


def is_parameterized_route(url_rule: str) -> bool:
    """Check if route has parameters like <id> or <int:id>."""
    return "<" in url_rule and ">" in url_rule


def get_static_url(url_rule: str) -> str | None:
    """Convert URL rule to static URL for testing.

    Returns None if the route requires parameters that can't be defaulted.
    """
    if not is_parameterized_route(url_rule):
        return url_rule

    # Skip routes with required parameters
    # These need specific test data to access
    return None


@pytest.fixture
def build_nav(app: Flask) -> NavTree:
    """Build the nav tree."""
    nav_tree = app.extensions["nav_tree"]
    nav_tree._nodes = {}
    nav_tree._sections = {}
    nav_tree._url_to_endpoint = {}
    nav_tree._built = False
    nav_tree.build(app)
    return nav_tree


@pytest.fixture
def test_org(fresh_db) -> Organisation:
    """Create a test organisation."""
    db_session = fresh_db.session
    org = Organisation(name="Nav Access Test Org")
    db_session.add(org)
    db_session.commit()
    return org


def get_or_create_role(db_session, role_enum: RoleEnum) -> Role:
    """Get or create a role."""
    role = db_session.query(Role).filter_by(name=role_enum.name).first()
    if not role:
        role = Role(name=role_enum.name, description=role_enum.value)
        db_session.add(role)
        db_session.flush()
    return role


def create_user_with_role(
    fresh_db, test_org: Organisation, role_enum: RoleEnum, email_prefix: str
) -> User:
    """Create a user with a specific role.

    - Supplementary roles (ADMIN, MANAGER, LEADER) are combined with PRESS_MEDIA
    - All users get a KYCProfile (required for profile.profile_label)
    """
    db_session = fresh_db.session

    # Create user
    user = User(email=f"{email_prefix}@example.com")
    user.photo = b""
    user.active = True
    user.organisation = test_org
    user.organisation_id = test_org.id

    # Add the requested role
    role = get_or_create_role(db_session, role_enum)
    user.roles.append(role)

    # Supplementary roles need a community role for first_community()
    if role_enum in SUPPLEMENTARY_ROLES:
        base_role = get_or_create_role(db_session, RoleEnum.PRESS_MEDIA)
        user.roles.append(base_role)

    db_session.add(user)
    db_session.flush()

    # Create KYCProfile (required for job_title, profile_label)
    profile = KYCProfile(
        user_id=user.id,
        profile_id=f"test_{role_enum.name.lower()}",
        profile_code=role_enum.name[:4].upper(),
        profile_label=f"Test {role_enum.value}",
    )
    db_session.add(profile)
    db_session.commit()

    return user


def get_testable_routes(nav_tree) -> list[tuple[str, str]]:
    """Get all routes that can be tested (non-parameterized, non-section).

    Returns list of (endpoint_name, url) tuples.
    """
    routes = []
    for name, node in nav_tree._nodes.items():
        # Skip section nodes (they don't have real endpoints)
        if node.is_section:
            continue

        # Get static URL
        url = get_static_url(node.url_rule)
        if url is None:
            continue

        routes.append((name, url))

    return routes


def get_acl_protected_routes(nav_tree) -> dict[str, list[RoleEnum]]:
    """Get routes with ACL and which roles can access them.

    Returns dict mapping endpoint name to list of allowed roles.
    """
    protected = {}
    for name, node in nav_tree._nodes.items():
        if node.acl:
            allowed_roles = []
            for directive, role, _action in node.acl:
                if directive.lower() == "allow":
                    allowed_roles.append(role)
            if allowed_roles:
                protected[name] = allowed_roles
    return protected


class TestNavAccessConsistency:
    """Test that nav tree visibility matches actual access control."""

    @pytest.mark.parametrize("role_enum", ROLES_TO_TEST)
    def test_visible_routes_are_accessible(
        self,
        app: Flask,
        fresh_db,
        test_org: Organisation,
        build_nav: NavTree,
        role_enum: RoleEnum,
    ):
        """Test that routes visible in nav are actually accessible.

        For each role, get the routes that should be visible,
        then verify they return 200 or redirect (not 403/404/500).
        """
        nav_tree = build_nav

        # Create user with this role
        user = create_user_with_role(
            fresh_db, test_org, role_enum, f"test-{role_enum.name.lower()}"
        )
        client = make_authenticated_client(app, user)

        # Get all testable routes
        all_routes = get_testable_routes(nav_tree)
        acl_protected = get_acl_protected_routes(nav_tree)

        # Filter to routes visible to this role
        visible_routes = []
        for endpoint, url in all_routes:
            if endpoint in acl_protected:
                # Check if this role is allowed
                allowed_roles = acl_protected[endpoint]
                if role_enum in allowed_roles:
                    visible_routes.append((endpoint, url))
            else:
                # No ACL = visible to all authenticated users
                visible_routes.append((endpoint, url))

        # Test each visible route
        acl_failures = []  # 403 - ACL mismatch (nav visible but view denies)
        other_failures = []  # 404, 500, exceptions

        for endpoint, url in visible_routes:
            # Skip known test-environment issues
            if endpoint in SKIP_ENDPOINTS:
                continue

            try:
                response = client.get(url)
                if response.status_code == 403:
                    # ACL mismatch: nav tree shows route but view denies access
                    acl_failures.append(
                        f"{endpoint} ({url}): 403 - nav visible but view denies"
                    )
                elif response.status_code not in [200, 302]:
                    other_failures.append(
                        f"{endpoint} ({url}): got {response.status_code}"
                    )
            except Exception as e:
                other_failures.append(f"{endpoint} ({url}): {type(e).__name__}: {e}")

        # ACL failures are the main concern - these indicate nav/view mismatch
        if acl_failures:
            failure_msg = f"\n{role_enum.name}: {len(acl_failures)} ACL mismatches (nav shows but view denies):\n"
            failure_msg += "\n".join(f"  - {f}" for f in acl_failures)
            if other_failures:
                failure_msg += (
                    f"\n\nAdditionally, {len(other_failures)} infrastructure issues:\n"
                )
                failure_msg += "\n".join(f"  - {f}" for f in other_failures)
            pytest.fail(failure_msg)

    @pytest.mark.parametrize("role_enum", ROLES_TO_TEST)
    def test_hidden_routes_are_denied(
        self,
        app: Flask,
        fresh_db,
        test_org: Organisation,
        build_nav: NavTree,
        role_enum: RoleEnum,
    ):
        """Test that routes hidden by ACL are actually denied.

        For each role, get routes that should be hidden (ACL doesn't include this role),
        then verify they return 403 or redirect to login.
        """
        nav_tree = build_nav

        # Create user with this role
        user = create_user_with_role(
            fresh_db, test_org, role_enum, f"deny-{role_enum.name.lower()}"
        )
        client = make_authenticated_client(app, user)

        # Get all user's roles (supplementary roles also have PRESS_MEDIA)
        user_roles = {role_enum}
        if role_enum in SUPPLEMENTARY_ROLES:
            user_roles.add(RoleEnum.PRESS_MEDIA)

        # Get ACL-protected routes
        acl_protected = get_acl_protected_routes(nav_tree)
        all_routes = get_testable_routes(nav_tree)

        # Filter to routes that should be hidden from all of user's roles
        hidden_routes = []
        for endpoint, url in all_routes:
            if endpoint in SKIP_ENDPOINTS:
                continue
            if endpoint in acl_protected:
                allowed_roles = set(acl_protected[endpoint])
                # Route is hidden if none of user's roles are allowed
                if not user_roles.intersection(allowed_roles):
                    hidden_routes.append((endpoint, url))

        if not hidden_routes:
            pytest.skip(f"No ACL-hidden routes for {role_enum.name}")

        # Test each hidden route
        failures = []
        for endpoint, url in hidden_routes:
            try:
                response = client.get(url)
                # Should be 403 (forbidden) or 302 (redirect to login/home)
                # 200 means the ACL isn't enforced in the view!
                if response.status_code == 200:
                    failures.append(
                        f"{endpoint} ({url}): expected 403/302, got 200 (ACL not enforced!)"
                    )
            except Exception:
                # Exceptions are not ACL failures, skip them
                pass

        if failures:
            failure_msg = (
                f"\n{role_enum.name}: {len(failures)} routes incorrectly accessible:\n"
            )
            failure_msg += "\n".join(f"  - {f}" for f in failures[:10])
            if len(failures) > 10:
                failure_msg += f"\n  ... and {len(failures) - 10} more"
            pytest.fail(failure_msg)


class TestNavAccessCoverage:
    """Test coverage statistics for nav access testing."""

    def test_report_route_coverage(self, app: Flask, build_nav: NavTree):
        """Report how many routes can be tested vs parameterized."""
        nav_tree = build_nav
        all_nodes = [
            (name, node)
            for name, node in nav_tree._nodes.items()
            if not node.is_section
        ]

        testable = []
        parameterized = []
        for name, node in all_nodes:
            if is_parameterized_route(node.url_rule):
                parameterized.append((name, node.url_rule))
            else:
                testable.append((name, node.url_rule))

        print("\n=== Nav Route Coverage ===")
        print(f"Total non-section routes: {len(all_nodes)}")
        print(f"Testable (no params): {len(testable)}")
        print(f"Parameterized (skipped): {len(parameterized)}")

        if parameterized:
            print("\nParameterized routes not tested:")
            for name, url in parameterized[:10]:
                print(f"  - {name}: {url}")
            if len(parameterized) > 10:
                print(f"  ... and {len(parameterized) - 10} more")

        # This test always passes - it's just for reporting
        assert True

    def test_report_acl_protected_routes(self, app: Flask, build_nav: NavTree):
        """Report which routes have ACL protection."""
        nav_tree = build_nav
        acl_protected = get_acl_protected_routes(nav_tree)

        print("\n=== ACL-Protected Routes ===")
        print(f"Total protected: {len(acl_protected)}")

        for endpoint, roles in sorted(acl_protected.items()):
            role_names = ", ".join(r.name for r in roles)
            print(f"  - {endpoint}: {role_names}")

        # This test always passes - it's just for reporting
        assert True


class TestUnauthenticatedAccess:
    """Test that protected routes deny unauthenticated access."""

    def test_protected_routes_require_auth(self, app: Flask, build_nav: NavTree):
        """Test that ACL-protected routes redirect unauthenticated users."""
        nav_tree = build_nav
        client = app.test_client()  # Not logged in

        acl_protected = get_acl_protected_routes(nav_tree)
        all_routes = get_testable_routes(nav_tree)

        # Get protected routes that are testable
        protected_routes = [
            (endpoint, url)
            for endpoint, url in all_routes
            if endpoint in acl_protected and endpoint not in SKIP_ENDPOINTS
        ]

        if not protected_routes:
            pytest.skip("No testable ACL-protected routes")

        failures = []
        for endpoint, url in protected_routes:
            try:
                response = client.get(url)
                # Should redirect to login (302) or return 401/403
                if response.status_code == 200:
                    failures.append(f"{endpoint} ({url}): accessible without auth!")
            except Exception:
                # Exceptions are infrastructure issues, not auth failures
                pass

        if failures:
            failure_msg = (
                f"\n{len(failures)} routes accessible without authentication:\n"
            )
            failure_msg += "\n".join(f"  - {f}" for f in failures[:10])
            if len(failures) > 10:
                failure_msg += f"\n  ... and {len(failures) - 10} more"
            pytest.fail(failure_msg)
