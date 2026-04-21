# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for cession-droits MVP v0: settings page + checkout guard."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models.business_wall import (
    BusinessWall,
    BWStatus,
)
from app.modules.wire.models import ArticlePost
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"rights_{uuid.uuid4().hex[:8]}@example.com"


def _make_user(db_session: Session, press_role: Role, org: Organisation) -> User:
    user = User(email=_unique_email(), active=True)
    user.photo = b""
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(press_role)
    db_session.add(user)
    db_session.commit()
    return user


def _make_media_bw(db_session: Session, owner: User, org: Organisation) -> BusinessWall:
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
        name=f"Media {uuid.uuid4().hex[:4]}",
    )
    db_session.add(bw)
    db_session.commit()
    return bw


@pytest.fixture
def press_role(db_session: Session) -> Role:
    role = Role(
        name=RoleEnum.PRESS_MEDIA.name,
        description=RoleEnum.PRESS_MEDIA.value,
    )
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def scenario(db_session: Session, press_role: Role) -> dict:
    seller_org = Organisation(name="Seller Media Org")
    buyer_org = Organisation(name="Buyer Media Org")
    db_session.add_all([seller_org, buyer_org])
    db_session.commit()

    seller = _make_user(db_session, press_role, seller_org)
    buyer = _make_user(db_session, press_role, buyer_org)

    seller_bw = _make_media_bw(db_session, seller, seller_org)
    buyer_bw = _make_media_bw(db_session, buyer, buyer_org)

    post = ArticlePost(
        title="Un article à céder",
        content="<p>Corps de l'article.</p>",
        owner_id=seller.id,
        publisher_id=seller_org.id,
        media_id=seller_org.id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.commit()

    return {
        "seller": seller,
        "seller_bw": seller_bw,
        "buyer": buyer,
        "buyer_bw": buyer_bw,
        "post": post,
    }


def test_settings_page_requires_owner(
    app: Flask, db_session: Session, press_role: Role, scenario: dict
):
    # Another media user without an owned BW tries to open the page.
    other_org = Organisation(name="Outsider Media")
    db_session.add(other_org)
    db_session.commit()
    outsider = _make_user(db_session, press_role, other_org)
    client = make_authenticated_client(app, outsider)

    response = client.get("/BW/rights-policy")
    assert response.status_code in (403, 404)


def test_settings_page_owner_can_save(app: Flask, db_session: Session, scenario: dict):
    # Owner of seller_bw saves a blacklist policy.
    client = make_authenticated_client(app, scenario["seller"])

    with patch(
        "app.modules.bw.bw_activation.routes.rights_policy.current_business_wall",
        return_value=scenario["seller_bw"],
    ):
        response = client.post(
            "/BW/rights-policy",
            data={
                "option": "blacklist",
                "media_ids": (
                    f"{scenario['buyer_bw'].id}\n\n00000000-0000-0000-0000-000000000999"
                ),
            },
            follow_redirects=False,
        )
    assert response.status_code == 302
    db_session.refresh(scenario["seller_bw"])
    assert scenario["seller_bw"].rights_sales_policy == {
        "option": "blacklist",
        "media_ids": [
            str(scenario["buyer_bw"].id),
            "00000000-0000-0000-0000-000000000999",
        ],
    }


def test_publishing_freezes_snapshot_then_guard_blocks_buyer(
    app: Flask, db_session: Session, scenario: dict
):
    # 1. Seller sets a whitelist that excludes buyer_bw.
    seller_bw = scenario["seller_bw"]
    seller_bw.rights_sales_policy = {
        "option": "whitelist",
        "media_ids": ["some-other-bw"],
    }
    db_session.commit()

    # 2. Seller publishes a new article — snapshot must freeze.
    new_post = ArticlePost(
        title="Post with frozen snapshot",
        content="<p>x</p>",
        owner_id=scenario["seller"].id,
        publisher_id=scenario["seller"].organisation_id,
        media_id=scenario["seller"].organisation_id,
        status=PublicationStatus.DRAFT,
    )
    db_session.add(new_post)
    db_session.commit()
    new_post.status = PublicationStatus.PUBLIC
    db_session.commit()

    assert new_post.rights_sales_snapshot == {
        "option": "whitelist",
        "media_ids": ["some-other-bw"],
    }

    # 3. Buyer tries to buy the cession — route refuses.
    client = make_authenticated_client(app, scenario["buyer"])
    app.config["STRIPE_LIVE_ENABLED"] = True
    try:
        with patch("stripe.checkout.Session.create") as mock_create:
            mock_create.return_value = MagicMock(url="https://stripe/x")
            response = client.post(
                f"/wire/{new_post.id}/buy/cession", follow_redirects=False
            )
        assert response.status_code == 302
        mock_create.assert_not_called()
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False


def test_guard_allows_whitelisted_buyer(
    app: Flask, db_session: Session, scenario: dict
):
    seller_bw = scenario["seller_bw"]
    buyer_bw = scenario["buyer_bw"]
    seller_bw.rights_sales_policy = {
        "option": "whitelist",
        "media_ids": [str(buyer_bw.id)],
    }
    db_session.commit()

    post = ArticlePost(
        title="OK to buy",
        content="<p>x</p>",
        owner_id=scenario["seller"].id,
        publisher_id=scenario["seller"].organisation_id,
        media_id=scenario["seller"].organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.commit()

    assert post.rights_sales_snapshot == {
        "option": "whitelist",
        "media_ids": [str(buyer_bw.id)],
    }

    client = make_authenticated_client(app, scenario["buyer"])
    app.config["STRIPE_LIVE_ENABLED"] = True
    app.config["STRIPE_PRICE_CESSION"] = "price_test"
    try:
        with (
            patch("stripe.checkout.Session.create") as mock_create,
            patch(
                "app.modules.wire.views.purchase.load_stripe_api_key",
                return_value=True,
            ),
        ):
            mock_create.return_value = MagicMock(url="https://stripe/x")
            response = client.post(
                f"/wire/{post.id}/buy/cession", follow_redirects=False
            )
        assert response.status_code == 303
        mock_create.assert_called_once()
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False
        app.config.pop("STRIPE_PRICE_CESSION", None)


def test_pre_mvp_post_still_buyable(app: Flask, db_session: Session, scenario: dict):
    """Posts published before the MVP have a NULL snapshot; they behave
    as `all_subscribed` (back-compat)."""
    post = scenario["post"]
    assert post.rights_sales_snapshot is not None  # was frozen at insert

    # Simulate pre-MVP by resetting the snapshot.
    post.rights_sales_snapshot = None
    db_session.commit()

    client = make_authenticated_client(app, scenario["buyer"])
    app.config["STRIPE_LIVE_ENABLED"] = True
    app.config["STRIPE_PRICE_CESSION"] = "price_test"
    try:
        with (
            patch("stripe.checkout.Session.create") as mock_create,
            patch(
                "app.modules.wire.views.purchase.load_stripe_api_key",
                return_value=True,
            ),
        ):
            mock_create.return_value = MagicMock(url="https://stripe/x")
            response = client.post(
                f"/wire/{post.id}/buy/cession", follow_redirects=False
            )
        assert response.status_code == 303
    finally:
        app.config["STRIPE_LIVE_ENABLED"] = False
        app.config.pop("STRIPE_PRICE_CESSION", None)
