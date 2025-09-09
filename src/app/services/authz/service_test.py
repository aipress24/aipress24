from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.enums import CommunityEnum, RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation

from .service import AuthorizationService

# --- Mocks and Test Data ---


@pytest.fixture
def mock_rbac_config() -> dict:
    """Provides a mock of the rbac.yaml configuration file."""
    return {
        "roles_by_bw_type": {
            "media": "media_member",
            "pr": "pr_agent_member",
        },
        "role_permissions": {
            "journalist": [
                "article:create",
                "article:publish",
                "newsroom:access",
            ],
            "admin": ["admin:access"],
            "media_member": ["newsroom_subject:create", "event:manage"],
            "pr_agent_member": [
                "press_release:create",
                "bw:manage_clients",
            ],
            "press_media": [  # Role from community
                "community:view_press_feed"
            ],
        },
    }


@pytest.fixture
def auth_service() -> AuthorizationService:
    """Provides an instance of the AuthorizationService."""
    return container.get(AuthorizationService)


@pytest.fixture
def setup_roles(db_session: scoped_session) -> dict[str, Role]:
    """Creates all necessary roles in the database for tests."""
    roles = {}
    role_names = [
        "ADMIN",
        "JOURNALIST",
        "PRESS_MEDIA",
        "PRESS_RELATIONS",
        "EXPERT",
        "TRANSFORMER",
        "ACADEMIC",
    ]
    for name in role_names:
        role = Role(name=name.upper(), description=f"{name} Role")
        db_session.add(role)
        roles[name.upper()] = role

    db_session.commit()
    return roles


# --- Test Cases ---


@patch("app.services.authz.service._load_rbac_config")
def test_get_roles_direct_assignment(
    mock_loader: MagicMock,
    db_session: scoped_session,
    auth_service: AuthorizationService,
    setup_roles: dict[str, Role],
    mock_rbac_config: dict,
):
    """Tests that directly assigned roles are correctly identified."""
    mock_loader.return_value = mock_rbac_config

    admin_user = User(email="admin@test.com", roles=[setup_roles["ADMIN"]])
    db_session.add(admin_user)
    db_session.commit()

    roles = auth_service.get_roles(admin_user)

    assert "ADMIN" in roles
    assert len(roles) == 1


@patch("app.services.authz.service._load_rbac_config")
def test_get_roles_community_inheritance(
    mock_loader: MagicMock,
    db_session: scoped_session,
    auth_service: AuthorizationService,
    mock_rbac_config: dict,
):
    """Tests that roles are correctly inherited from the user's KYC community."""
    mock_loader.return_value = mock_rbac_config

    journalist_profile = KYCProfile(profile_community=CommunityEnum.PRESS_MEDIA.name)
    journalist_user = User(email="journalist@test.com", profile=journalist_profile)
    db_session.add(journalist_user)
    db_session.commit()

    roles = auth_service.get_roles(journalist_user)

    assert RoleEnum.PRESS_MEDIA.name in roles
    assert len(roles) == 1


@patch("app.services.authz.service._load_rbac_config")
def test_get_roles_bw_type_inheritance(
    mock_loader: MagicMock,
    db_session: scoped_session,
    auth_service: AuthorizationService,
    mock_rbac_config: dict,
):
    """Tests that roles are correctly inherited from the organization's BW type."""
    mock_loader.return_value = mock_rbac_config

    media_org = Organisation(name="Test Media", bw_type="media")
    pr_org = Organisation(name="Test PR", bw_type="pr")

    media_user = User(email="media_user@test.com", organisation=media_org)
    pr_user = User(email="pr_user@test.com", organisation=pr_org)

    db_session.add_all([media_org, pr_org, media_user, pr_user])
    db_session.commit()

    media_roles = auth_service.get_roles(media_user)
    pr_roles = auth_service.get_roles(pr_user)

    assert "media_member" in media_roles
    assert "pr_agent_member" in pr_roles


@patch("app.services.authz.service._load_rbac_config")
def test_get_roles_aggregation(
    mock_loader: MagicMock,
    db_session: scoped_session,
    auth_service: AuthorizationService,
    setup_roles: dict[str, Role],
    mock_rbac_config: dict,
):
    """Tests the aggregation of roles from all sources."""
    mock_loader.return_value = mock_rbac_config

    media_org = Organisation(name="Complex Media", bw_type="media")
    profile = KYCProfile(profile_community=CommunityEnum.PRESS_MEDIA.name)

    complex_user = User(
        email="complex@test.com",
        roles=[setup_roles["JOURNALIST"]],
        organisation=media_org,
        profile=profile,
    )
    db_session.add_all([media_org, complex_user])
    db_session.commit()

    roles = auth_service.get_roles(complex_user)

    assert roles == {"JOURNALIST", "PRESS_MEDIA", "media_member"}


@patch("app.services.authz.service._load_rbac_config")
def test_get_permissions(
    mock_loader: MagicMock,
    db_session: scoped_session,
    auth_service: AuthorizationService,
    setup_roles: dict[str, Role],
    mock_rbac_config: dict,
):
    """Tests that permissions are correctly aggregated from all user roles."""
    mock_loader.return_value = mock_rbac_config

    media_org = Organisation(name="Complex Media", bw_type="media")
    profile = KYCProfile(profile_community=CommunityEnum.PRESS_MEDIA.name)

    complex_user = User(
        email="complex@test.com",
        roles=[setup_roles["JOURNALIST"]],
        organisation=media_org,
        profile=profile,
    )
    db_session.add_all([media_org, complex_user])
    db_session.commit()

    permissions = auth_service.get_permissions(complex_user)

    expected_permissions = {
        "article:create",
        "article:publish",
        "newsroom:access",  # from JOURNALIST role
        "community:view_press_feed",  # from PRESS_MEDIA community
        "newsroom_subject:create",
        "event:manage",  # from media_member (BW type)
    }
    assert permissions == expected_permissions


@patch("app.services.authz.service._load_rbac_config")
def test_can_method(
    mock_loader: MagicMock,
    db_session: scoped_session,
    auth_service: AuthorizationService,
    setup_roles: dict[str, Role],
    mock_rbac_config: dict,
):
    """Tests the `can` method for positive and negative cases."""
    mock_loader.return_value = mock_rbac_config

    journalist = User(email="journalist@test.com", roles=[setup_roles["JOURNALIST"]])
    admin = User(email="admin@test.com", roles=[setup_roles["ADMIN"]])

    db_session.add_all([journalist, admin])
    db_session.commit()

    assert auth_service.can(journalist, "article:publish")
    assert not auth_service.can(journalist, "admin:access")
    assert auth_service.can(admin, "admin:access")
    assert not auth_service.can(admin, "article:publish")

    # Test with anonymous user
    assert not auth_service.can(None, "article:publish")


@patch("app.services.authz.service._load_rbac_config")
def test_has_role_method(
    mock_loader: MagicMock,
    db_session: scoped_session,
    auth_service: AuthorizationService,
    setup_roles: dict[str, Role],
    mock_rbac_config: dict,
):
    """Tests the `has_role` method for positive and negative cases."""
    mock_loader.return_value = mock_rbac_config

    media_org = Organisation(name="Complex Media", bw_type="media")
    profile = KYCProfile(profile_community=CommunityEnum.PRESS_MEDIA.name)

    complex_user = User(
        email="complex@test.com",
        roles=[setup_roles["JOURNALIST"]],
        organisation=media_org,
        profile=profile,
    )
    db_session.add_all([media_org, complex_user])
    db_session.commit()

    assert auth_service.has_role(complex_user, "JOURNALIST") is True
    assert auth_service.has_role(complex_user, "media_member") is True
    assert auth_service.has_role(complex_user, "PRESS_MEDIA") is True
    assert auth_service.has_role(complex_user, "ADMIN") is False

    # Test with anonymous user
    assert auth_service.has_role(None, "JOURNALIST") is False
