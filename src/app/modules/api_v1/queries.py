# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Thin read adapter over the domain repositories.

This module owns *no* visibility logic. Each function resolves the relevant
domain repository and calls its published/public/active read, so "what is
publicly visible" is defined once, in the domain (see
``app.models.content.visibility`` and the repositories' ``*_filters``),
and the API cannot drift from it.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from svcs.flask import container

from app.flask.extensions import db
from app.models.repositories import OrganisationRepository, UserRepository
from app.modules.bw.bw_activation.models.repositories import BusinessWallRepository
from app.modules.events.repositories import EventPostRepository
from app.modules.wire.repositories import (
    ArticlePostRepository,
    PressReleasePostRepository,
)

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.organisation import Organisation
    from app.modules.bw.bw_activation.models.business_wall import BusinessWall
    from app.modules.events.models import EventPost
    from app.modules.wire.models import ArticlePost, PressReleasePost

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

Page = tuple[list, int, int, int]  # (rows, total, limit, offset)


def clamp_limit(limit: int) -> int:
    return max(1, min(int(limit), MAX_LIMIT))


def clamp_offset(offset: int) -> int:
    return max(0, int(offset))


def _page(result: tuple, limit: int, offset: int) -> Page:
    rows, total = result
    return list(rows), total, limit, offset


# --- news content (articles & press releases) -----------------------------


def list_articles(limit: int, offset: int) -> Page:
    limit, offset = clamp_limit(limit), clamp_offset(offset)
    repo = container.get(ArticlePostRepository)
    return _page(repo.list_published(limit=limit, offset=offset), limit, offset)


def get_article(identifier: int) -> ArticlePost | None:
    return container.get(ArticlePostRepository).get_published(identifier)


def list_press_releases(limit: int, offset: int) -> Page:
    limit, offset = clamp_limit(limit), clamp_offset(offset)
    repo = container.get(PressReleasePostRepository)
    return _page(repo.list_published(limit=limit, offset=offset), limit, offset)


def get_press_release(identifier: int) -> PressReleasePost | None:
    return container.get(PressReleasePostRepository).get_published(identifier)


# --- events ---------------------------------------------------------------


def list_events(limit: int, offset: int) -> Page:
    limit, offset = clamp_limit(limit), clamp_offset(offset)
    repo = container.get(EventPostRepository)
    return _page(repo.list_published(limit=limit, offset=offset), limit, offset)


def get_event(identifier: int) -> EventPost | None:
    return container.get(EventPostRepository).get_published(identifier)


# --- organisations --------------------------------------------------------


def list_organisations(limit: int, offset: int) -> Page:
    limit, offset = clamp_limit(limit), clamp_offset(offset)
    repo = container.get(OrganisationRepository)
    return _page(repo.list_public(limit=limit, offset=offset), limit, offset)


def get_organisation(identifier: int) -> Organisation | None:
    return container.get(OrganisationRepository).get_public(identifier)


# --- business walls -------------------------------------------------------
# BusinessWallRepository is not svcs-registered (bw uses the advanced-alchemy
# service layer), so it is instantiated directly against the request session.


def list_business_walls(limit: int, offset: int) -> Page:
    limit, offset = clamp_limit(limit), clamp_offset(offset)
    repo = BusinessWallRepository(session=db.session)
    return _page(repo.list_active(limit=limit, offset=offset), limit, offset)


def get_business_wall(identifier: str) -> BusinessWall | None:
    try:
        bw_id = uuid.UUID(str(identifier))
    except (ValueError, AttributeError):
        return None
    return BusinessWallRepository(session=db.session).get_active(bw_id)


# --- members (curated public profiles) ------------------------------------


def list_members(limit: int, offset: int) -> Page:
    limit, offset = clamp_limit(limit), clamp_offset(offset)
    repo = container.get(UserRepository)
    return _page(repo.list_public_members(limit=limit, offset=offset), limit, offset)


def get_member(identifier: int) -> User | None:
    return container.get(UserRepository).get_public_member(identifier)
