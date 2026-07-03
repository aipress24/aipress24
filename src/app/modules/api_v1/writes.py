# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Write orchestration for the public API (the imperative shell over the domain).

This is the write twin of :mod:`.queries`. It re-uses the *exact* WIP-room
authorization predicates and the source models' publication state machines
plus their blinker signals, so an API publish is indistinguishable from a UI
publish: same public wire/event mirror, same search index, same
rights/monetization snapshot. Nothing about who-may-publish or
what-becomes-visible is re-implemented here — it is all delegated to the
domain, so the API cannot drift from the portal.

Three content types, three authorization gates (all owner-scoped: every
mutation targets a row already resolved through ``OwnedRepository.get_owned``):

- **press releases** (communiqués): ``user_can_access_comroom`` +
  ``can_user_publish_for`` (own org, or a client org via partnership — the
  "agence de RP" on-behalf case);
- **articles** (newsroom): ``user_can_access_newsroom`` (journalists only) and
  strictly own-organisation attribution — no on-behalf path exists in the UI;
- **events** (eventroom): ``user_can_access_eventroom`` (+ the ``EVENTS``
  mission when acting as a PR manager) and, like press releases, optional
  on-behalf attribution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from arrow import now
from sqlalchemy import select
from svcs.flask import container

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.logging import report_failure
from app.models.lifecycle import PublicationStatus
from app.modules.bw.bw_activation.models import PermissionType
from app.modules.bw.bw_activation.models.business_wall import BusinessWall
from app.modules.bw.bw_activation.user_utils import can_user_publish_for
from app.modules.wip.models import (
    Article,
    ArticleRepository,
    Communique,
    CommuniqueRepository,
)
from app.modules.wip.models.eventroom import Event, EventRepository
from app.modules.wip.pr_access import (
    pr_manager_missing_mission,
    user_can_access_comroom,
    user_can_access_eventroom,
    user_can_access_newsroom,
    user_has_mission,
    user_is_acting_as_pr_manager,
)
from app.modules.wip.services.pr_notifications import (
    absolute_url_for,
    notify_client_of_pr_publication,
)
from app.services.html_sanitize import sanitize_html
from app.signals import (
    article_published,
    article_unpublished,
    article_updated,
    communique_published,
    communique_unpublished,
    communique_updated,
    event_published,
    event_unpublished,
    event_updated,
)

if TYPE_CHECKING:
    from blinker import Signal

    from app.models.auth import User

# Only ``contenu`` (the HTML body) is sanitized here — the model sanitizes it
# too (idempotent), and doing it in the API also closes the "echo the unsaved
# value back before commit" gap. ``titre``/``chapo``/``brief`` are stored
# verbatim, exactly as the UI does: they are rendered escaped, and running an
# HTML sanitizer over them would entity-encode plain text (e.g. "R&D").
_SANITIZED_FIELDS = frozenset({"contenu"})

_PRESS_RELEASE_FIELDS = (
    "titre",
    "chapo",
    "contenu",
    "genre",
    "section",
    "topic",
    "sector",
    "geo_localisation",
    "language",
    "address",
    "pays_zip_ville",
)
_ARTICLE_FIELDS = (
    "titre",
    "chapo",
    "contenu",
    "brief",
    "copyright",
    "genre",
    "section",
    "topic",
    "sector",
    "geo_localisation",
    "language",
    "address",
    "pays_zip_ville",
)
_EVENT_FIELDS = (
    "titre",
    "chapo",
    "contenu",
    "event_type",
    "sector",
    "address",
    "pays_zip_ville",
    "url",
    "language",
)


class WriteError(Exception):
    """A write was refused; ``status`` is the HTTP code the resource returns."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(message)


# --- press releases (communiqués) -----------------------------------------


def create_press_release(user: User, data: dict) -> Communique:
    """Create a DRAFT press release owned by ``user``."""
    _require_comroom(user)
    publisher_id = _resolve_publisher(
        user, data.get("publisher_id"), PermissionType.PRESS_RELEASE
    )
    model = Communique(
        owner=user, status=PublicationStatus.DRAFT, publisher_id=publisher_id
    )
    _apply_fields(model, data, _PRESS_RELEASE_FIELDS)
    if "embargoed_until" in data:
        model.embargoed_until = data["embargoed_until"]
    return _create(model, container.get(CommuniqueRepository), communique_updated)


def update_press_release(user: User, model: Communique, data: dict) -> Communique:
    """Apply a partial update to the caller's own press release."""
    _require_comroom(user)
    if "publisher_id" in data:
        model.publisher_id = _resolve_publisher(
            user, data["publisher_id"], PermissionType.PRESS_RELEASE
        )
    _apply_fields(model, data, _PRESS_RELEASE_FIELDS)
    if "embargoed_until" in data:
        model.embargoed_until = data["embargoed_until"]
    return _save(model, container.get(CommuniqueRepository), communique_updated)


def publish_press_release(user: User, model: Communique) -> Communique:
    """Publish the caller's own press release (attributed to its publisher)."""
    _require_comroom(user)
    publisher_id = _resolve_publisher(
        user, model.publisher_id, PermissionType.PRESS_RELEASE
    )
    _publish(
        model, publisher_id, container.get(CommuniqueRepository), communique_published
    )
    _notify_client_on_behalf(user, model, "communiqué", "CommuniquesWipView:get")
    return model


def unpublish_press_release(user: User, model: Communique) -> Communique:
    """Return the caller's own press release to DRAFT and take its mirror down."""
    _require_comroom(user)
    _unpublish(model, container.get(CommuniqueRepository), communique_unpublished)
    return model


def delete_press_release(user: User, model: Communique) -> None:
    """Soft-delete the caller's own press release."""
    _require_comroom(user)
    _delete(model, container.get(CommuniqueRepository), communique_unpublished)


# --- articles (newsroom) --------------------------------------------------
# Own-organisation only: media/publisher are the journalist's own org, set
# server-side. There is no on-behalf path (the UI has none for articles).


def create_article(user: User, data: dict) -> Article:
    """Create a DRAFT article owned by ``user`` (own-org attribution)."""
    _require_newsroom(user)
    org_id = user.organisation_id
    if not org_id:
        raise WriteError(
            422, "Your account has no organisation to attribute the article to."
        )
    model = Article(
        owner=user,
        commanditaire_id=user.id,
        media_id=org_id,
        publisher_id=org_id,
        status=PublicationStatus.DRAFT,
        date_parution_prevue=data.get("date_parution_prevue") or now(LOCAL_TZ),
    )
    _apply_fields(model, data, _ARTICLE_FIELDS)
    return _create(model, container.get(ArticleRepository), article_updated)


def update_article(user: User, model: Article, data: dict) -> Article:
    """Apply a partial update to the caller's own article."""
    _require_newsroom(user)
    if data.get("date_parution_prevue"):
        model.date_parution_prevue = data["date_parution_prevue"]
    _apply_fields(model, data, _ARTICLE_FIELDS)
    return _save(model, container.get(ArticleRepository), article_updated)


def publish_article(user: User, model: Article) -> Article:
    """Publish the caller's own article (attributed to its own organisation)."""
    _require_newsroom(user)
    _publish(
        model,
        user.organisation_id or None,
        container.get(ArticleRepository),
        article_published,
    )
    return model


def unpublish_article(user: User, model: Article) -> Article:
    """Return the caller's own article to DRAFT and take its mirror down."""
    _require_newsroom(user)
    _unpublish(model, container.get(ArticleRepository), article_unpublished)
    return model


def delete_article(user: User, model: Article) -> None:
    """Soft-delete the caller's own article."""
    _require_newsroom(user)
    _delete(model, container.get(ArticleRepository), article_unpublished)


# --- events (eventroom) ---------------------------------------------------
# Like press releases: optional on-behalf attribution via publisher_id.


def create_event(user: User, data: dict) -> Event:
    """Create a DRAFT event owned by ``user``."""
    _require_eventroom(user)
    publisher_id = _resolve_publisher(
        user, data.get("publisher_id"), PermissionType.EVENTS
    )
    model = Event(owner=user, status=PublicationStatus.DRAFT, publisher_id=publisher_id)
    _apply_fields(model, data, _EVENT_FIELDS)
    _apply_schedule(model, data)
    return _create(model, container.get(EventRepository), event_updated)


def update_event(user: User, model: Event, data: dict) -> Event:
    """Apply a partial update to the caller's own event."""
    _require_eventroom(user)
    if "publisher_id" in data:
        model.publisher_id = _resolve_publisher(
            user, data["publisher_id"], PermissionType.EVENTS
        )
    _apply_fields(model, data, _EVENT_FIELDS)
    _apply_schedule(model, data)
    return _save(model, container.get(EventRepository), event_updated)


def publish_event(user: User, model: Event) -> Event:
    """Publish the caller's own event (requires start/end times, via the domain)."""
    _require_eventroom(user)
    publisher_id = _resolve_publisher(user, model.publisher_id, PermissionType.EVENTS)
    _publish(model, publisher_id, container.get(EventRepository), event_published)
    _notify_client_on_behalf(user, model, "événement", "EventsWipView:get")
    return model


def unpublish_event(user: User, model: Event) -> Event:
    """Return the caller's own event to DRAFT and take its mirror down."""
    _require_eventroom(user)
    _unpublish(model, container.get(EventRepository), event_unpublished)
    return model


def delete_event(user: User, model: Event) -> None:
    """Soft-delete the caller's own event."""
    _require_eventroom(user)
    _delete(model, container.get(EventRepository), event_unpublished)


# --- shared publication mechanics -----------------------------------------
# Transaction order for publish/unpublish/delete mirrors the WIP CBVs:
# repo.update(auto_commit=False) -> signal.send -> db.session.commit(), because
# the mirror/search receivers flush into the same transaction.


def _create(model, repo, updated_signal):
    repo.add(model, auto_commit=True)
    updated_signal.send(model)
    db.session.commit()
    return model


def _save(model, repo, updated_signal):
    repo.update(model, auto_commit=False)
    updated_signal.send(model)
    db.session.commit()
    return model


def _publish(model, publisher_id, repo, published_signal: Signal) -> None:
    try:
        model.publish(publisher_id=publisher_id)
    except ValueError as exc:
        raise WriteError(422, str(exc)) from exc
    repo.update(model, auto_commit=False)
    published_signal.send(model)
    db.session.commit()


def _unpublish(model, repo, unpublished_signal: Signal) -> None:
    try:
        model.unpublish()
    except ValueError as exc:
        raise WriteError(422, str(exc)) from exc
    repo.update(model, auto_commit=False)
    unpublished_signal.send(model)
    db.session.commit()


def _delete(model, repo, unpublished_signal: Signal) -> None:
    # Re-emit unpublish first so a published source takes its public mirror
    # down (no-op if never published), then soft-delete.
    unpublished_signal.send(model)
    model.deleted_at = now(LOCAL_TZ)
    repo.update(model, auto_commit=True)


# --- authorization & field helpers ----------------------------------------


def _require_comroom(user: User) -> None:
    """The Com'room entry gate, identical to ``CommuniquesWipView.before_request``."""
    if not user_can_access_comroom(user):
        raise WriteError(403, "Your account is not allowed to author press releases.")
    if user_is_acting_as_pr_manager(user) and not user_has_mission(
        user, PermissionType.PRESS_RELEASE
    ):
        raise WriteError(
            403, "You lack the PRESS_RELEASE mission on the selected Business Wall."
        )


def _require_newsroom(user: User) -> None:
    """The Newsroom author gate: journalists only (no on-behalf)."""
    if not user_can_access_newsroom(user):
        raise WriteError(
            403, "Your account is not allowed to author articles (journalists only)."
        )


def _require_eventroom(user: User) -> None:
    """The Eventroom entry gate, identical to ``EventsWipView.before_request``."""
    if not user_can_access_eventroom(user):
        raise WriteError(403, "Your account is not allowed to author events.")
    if user_is_acting_as_pr_manager(user) and not user_has_mission(
        user, PermissionType.EVENTS
    ):
        raise WriteError(
            403, "You lack the EVENTS mission on the selected Business Wall."
        )


def _resolve_publisher(
    user: User, publisher_id: int | None, mission: PermissionType
) -> int | None:
    """Default to the caller's own org; reject an org they can't publish for.

    Two gates, both mirroring the portal:
    - ``can_user_publish_for``: the caller must be entitled to the org at all
      (own org, a PR-manager role on its BW, or an active agency partnership);
    - ``pr_manager_missing_mission``: a *delegated* PR manager (someone whose
      entitlement comes from a ``BWPRi``/``BWPRe`` role) must additionally hold
      the granular ``mission`` (PRESS_RELEASE / EVENTS) on the target org's BW —
      exactly the ``before_request`` gate the portal applies against the
      selected BW. This closes the gap where ``publisher_id`` (a free input) was
      decoupled from the mission check keyed to the session-selected BW.
    """
    publisher_id = publisher_id or user.organisation_id
    if publisher_id and not can_user_publish_for(user, publisher_id):
        raise WriteError(403, "You are not allowed to publish for this organisation.")
    if publisher_id and publisher_id != user.organisation_id:
        bws = _business_walls_for_org(publisher_id)
        if pr_manager_missing_mission(bws, user.id, mission):
            raise WriteError(
                403, "You lack the mission required to publish for this organisation."
            )
    return publisher_id


def _business_walls_for_org(org_id: int) -> list[BusinessWall]:
    return list(
        db.session.scalars(
            select(BusinessWall).where(BusinessWall.organisation_id == org_id)
        )
    )


def _apply_fields(model, data: dict, fields: tuple[str, ...]) -> None:
    for name in fields:
        if name in data:
            value = data[name]
            if name in _SANITIZED_FIELDS:
                value = str(sanitize_html(value))
            setattr(model, name, value)


def _apply_schedule(model: Event, data: dict) -> None:
    if "start_time" in data:
        model.start_time = data["start_time"]
    if "end_time" in data:
        model.end_time = data["end_time"]


def _notify_client_on_behalf(
    user: User, model, content_type: str, endpoint: str
) -> None:
    """Notify the client BW owner when an agency publishes on their behalf."""
    if not (
        model.publisher
        and user.organisation_id
        and model.publisher_id != user.organisation_id
    ):
        return
    try:
        notify_client_of_pr_publication(
            author=user,
            client_org=model.publisher,
            content_type=content_type,
            content_title=model.titre,
            content_url=absolute_url_for(endpoint, id=model.id),
        )
    except Exception as exc:
        report_failure(f"PR publication notif failed ({content_type} {model.id})", exc)
