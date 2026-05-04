# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for cession-droits MVP v0 helpers and snapshot hook."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models.business_wall import (
    BusinessWall,
    BWStatus,
)
from app.modules.bw.bw_activation.rights_policy import (
    DEFAULT_POLICY,
    get_policy,
    is_eligible_for_cession,
)
from app.modules.wire.models import ArticlePost

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"rp_{uuid.uuid4().hex[:8]}@example.com"


def _make_media_bw(
    db_session: Session,
    owner: User,
    org: Organisation,
    policy: dict | None = None,
) -> BusinessWall:
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
        name=f"Media Org {uuid.uuid4().hex[:4]}",
    )
    if policy is not None:
        bw.rights_sales_policy = policy
    db_session.add(bw)
    db_session.flush()
    return bw


@pytest.fixture
def seller_and_buyer(
    db_session: Session,
) -> tuple[User, BusinessWall, User, BusinessWall, Organisation]:
    """Return (seller, seller_bw, buyer, buyer_bw, seller_org)."""
    seller_org = Organisation(name="Seller Org")
    buyer_org = Organisation(name="Buyer Org")
    db_session.add_all([seller_org, buyer_org])
    db_session.flush()

    seller = User(email=_unique_email(), active=True)
    seller.organisation = seller_org
    seller.organisation_id = seller_org.id
    buyer = User(email=_unique_email(), active=True)
    buyer.organisation = buyer_org
    buyer.organisation_id = buyer_org.id
    db_session.add_all([seller, buyer])
    db_session.flush()

    seller_bw = _make_media_bw(db_session, seller, seller_org)
    buyer_bw = _make_media_bw(db_session, buyer, buyer_org)

    return seller, seller_bw, buyer, buyer_bw, seller_org


def test_get_policy_default_when_unconfigured(db_session: Session, seller_and_buyer):
    _, seller_bw, *_ = seller_and_buyer
    assert get_policy(seller_bw) == DEFAULT_POLICY
    assert get_policy(None) == DEFAULT_POLICY


def test_get_policy_normalizes_media_ids_to_str(db_session: Session, seller_and_buyer):
    _, seller_bw, *_ = seller_and_buyer
    seller_bw.rights_sales_policy = {
        "option": "whitelist",
        "media_ids": [123, "abc"],
    }
    db_session.flush()
    result = get_policy(seller_bw)
    assert result == {"option": "whitelist", "media_ids": ["123", "abc"]}


def test_snapshot_frozen_on_publish(db_session: Session, seller_and_buyer):
    seller, seller_bw, *_ = seller_and_buyer
    seller_bw.rights_sales_policy = {
        "option": "blacklist",
        "media_ids": ["xyz"],
    }
    db_session.flush()

    post = ArticlePost(
        title="hello",
        content="<p>body</p>",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        media_id=seller.organisation_id,
        status=PublicationStatus.DRAFT,
    )
    db_session.add(post)
    db_session.flush()
    assert post.rights_sales_snapshot is None

    post.status = PublicationStatus.PUBLIC
    db_session.flush()

    assert post.rights_sales_snapshot == {
        "option": "blacklist",
        "media_ids": ["xyz"],
    }


def test_snapshot_not_overwritten_on_subsequent_edit(
    db_session: Session, seller_and_buyer
):
    seller, seller_bw, *_ = seller_and_buyer
    post = ArticlePost(
        title="hello",
        content="<p>body</p>",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        media_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()
    first_snapshot = dict(post.rights_sales_snapshot or {})

    # Editor changes policy after publishing.
    seller_bw.rights_sales_policy = {"option": "none", "media_ids": []}
    post.title = "updated"
    db_session.flush()

    assert post.rights_sales_snapshot == first_snapshot


def test_eligibility_all_subscribed(db_session: Session, seller_and_buyer):
    seller, _, buyer, _, _ = seller_and_buyer
    post = ArticlePost(
        title="t",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is True


def test_eligibility_whitelist(db_session: Session, seller_and_buyer):
    seller, seller_bw, buyer, buyer_bw, _ = seller_and_buyer
    seller_bw.rights_sales_policy = {
        "option": "whitelist",
        "media_ids": [str(buyer_bw.id)],
    }
    db_session.flush()

    post = ArticlePost(
        title="t",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        media_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is True

    # Change the snapshot manually to simulate a whitelist that excludes
    # the buyer.
    post.rights_sales_snapshot = {
        "option": "whitelist",
        "media_ids": ["some-other-bw"],
    }
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is False


def test_eligibility_blacklist(db_session: Session, seller_and_buyer):
    seller, _, buyer, buyer_bw, _ = seller_and_buyer
    post = ArticlePost(
        title="t",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    post.rights_sales_snapshot = {
        "option": "blacklist",
        "media_ids": [str(buyer_bw.id)],
    }
    db_session.add(post)
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is False


def test_eligibility_none(db_session: Session, seller_and_buyer):
    seller, _, buyer, _, _ = seller_and_buyer
    post = ArticlePost(
        title="t",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    post.rights_sales_snapshot = {"option": "none", "media_ids": []}
    db_session.add(post)
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is False


def test_eligibility_buyer_without_media_bw(db_session: Session, seller_and_buyer):
    seller, _, buyer, buyer_bw, _ = seller_and_buyer
    # Demote buyer's BW to a non-media type.
    buyer_bw.bw_type = "pr"
    db_session.flush()

    post = ArticlePost(
        title="t",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is False


def test_eligibility_null_snapshot_treated_as_all_subscribed(
    db_session: Session, seller_and_buyer
):
    """Pre-MVP posts have a Null snapshot; buyers should stay eligible."""
    seller, _, buyer, _, _ = seller_and_buyer
    post = ArticlePost(
        title="legacy",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()

    # Force snapshot back to None to simulate pre-MVP data.
    post.rights_sales_snapshot = None
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is True


# ─── BW Micro as rights holder (bug #0112 follow-up) ────────────


def _make_micro_bw(
    db_session: Session,
    owner: User,
    org: Organisation,
    policy: dict | None = None,
) -> BusinessWall:
    """Build an active BW of type ``micro`` — the
    journalist-in-micro-entreprise scenario where the journalist
    themselves owns the rights to their content."""
    bw = BusinessWall(
        bw_type="micro",
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
        name=f"Micro Org {uuid.uuid4().hex[:4]}",
    )
    if policy is not None:
        bw.rights_sales_policy = policy
    db_session.add(bw)
    db_session.flush()
    return bw


def test_eligibility_buyer_with_micro_bw_can_buy(db_session: Session):
    """A buyer holding a BW of type ``micro`` is eligible — same
    as a media-BW buyer."""
    seller_org = Organisation(name="Seller Media Org")
    buyer_org = Organisation(name="Buyer Micro Org")
    db_session.add_all([seller_org, buyer_org])
    db_session.flush()

    seller = User(email=_unique_email(), active=True)
    seller.organisation = seller_org
    seller.organisation_id = seller_org.id
    buyer = User(email=_unique_email(), active=True)
    buyer.organisation = buyer_org
    buyer.organisation_id = buyer_org.id
    db_session.add_all([seller, buyer])
    db_session.flush()

    _make_media_bw(db_session, seller, seller_org)
    _make_micro_bw(db_session, buyer, buyer_org)

    post = ArticlePost(
        title="t",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()

    # Default snapshot (all_subscribed) → micro-BW buyer is in.
    assert is_eligible_for_cession(buyer, post) is True


def test_eligibility_micro_seller_policy_honoured(
    db_session: Session,
):
    """A journalist with a ``micro`` BW publishes a post ; their
    rights-sales policy should be honoured by buyers (the
    `none` option blocks every cession)."""
    seller_org = Organisation(name="Seller Micro Org")
    buyer_org = Organisation(name="Buyer Media Org")
    db_session.add_all([seller_org, buyer_org])
    db_session.flush()

    seller = User(email=_unique_email(), active=True)
    seller.organisation = seller_org
    seller.organisation_id = seller_org.id
    buyer = User(email=_unique_email(), active=True)
    buyer.organisation = buyer_org
    buyer.organisation_id = buyer_org.id
    db_session.add_all([seller, buyer])
    db_session.flush()

    seller_bw = _make_micro_bw(db_session, seller, seller_org)
    _make_media_bw(db_session, buyer, buyer_org)

    seller_bw.rights_sales_policy = {
        "option": "none",
        "media_ids": [],
    }
    db_session.flush()

    post = ArticlePost(
        title="t",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is False


def test_eligibility_buyer_without_rights_holder_bw(
    db_session: Session, seller_and_buyer
):
    """A buyer whose only BW is `pr` (not in `_RIGHTS_HOLDER_BW_TYPES`)
    is NOT eligible. Pins the « only media + micro hold rights » rule."""
    seller, _, buyer, buyer_bw, _ = seller_and_buyer
    buyer_bw.bw_type = "pr"
    db_session.flush()

    post = ArticlePost(
        title="t",
        content="x",
        owner_id=seller.id,
        publisher_id=seller.organisation_id,
        status=PublicationStatus.PUBLIC,
    )
    db_session.add(post)
    db_session.flush()

    assert is_eligible_for_cession(buyer, post) is False
