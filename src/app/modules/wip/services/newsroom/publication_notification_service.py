# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Service for the « Notification de publication » workflow.

Called by the Newsroom views (mode A — from an existing avis
d'enquête — and mode B — free-form recipient targeting). Creates the
`NotificationPublication` + per-contact rows, posts the in-app
notifications and sends one transactional email per recipient.

Policy decisions frozen by SF (2026-04-24) :

- mode A pre-checks only the contacts whose status is `ACCEPTE` or
  `ACCEPTE_RELATION_PRESSE` ;
- mode B accepts any active AiPRESS24 user ;
- anti-spam cap : ``SPAM_CAP`` publication notifications per recipient
  on a rolling ``SPAM_WINDOW_DAYS``-day window ;
- anti-duplicate : same ``(article_url, recipient)`` can't be notified
  twice within ``DEDUP_WINDOW_DAYS`` (DB unique constraint enforces
  the one-per-publication half).

Spec : `local-notes/specs/notification-publication.md`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from flask_super.decorators import service
from sqlalchemy import func, select
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.modules.bw.bw_activation.user_utils import resolve_user_bw_name
from app.modules.wip.models import (
    AvisEnquete,
    ContactAvisEnquete,
    NotificationPublication,
    NotificationPublicationContact,
    StatutAvis,
)
from app.services.emails import PublicationNotificationMail
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.wip.models.newsroom import Article


SPAM_CAP = 5
SPAM_WINDOW_DAYS = 30
DEDUP_WINDOW_DAYS = 7

UrlBuilder = Callable[[NotificationPublication], str]
_NO_URL: UrlBuilder = lambda _n: ""  # noqa: E731


class PublicationNotificationError(ValueError):
    """User-facing validation error (empty URL, ownership violation)."""


@service
class PublicationNotificationService:
    def __init__(self) -> None:
        self._session = container.get(scoped_session)

    # --------------------------------------------------------------
    # Public entry points
    # --------------------------------------------------------------

    def contacts_for_avis(self, avis: AvisEnquete) -> list[ContactAvisEnquete]:
        stmt = (
            select(ContactAvisEnquete)
            .where(ContactAvisEnquete.avis_enquete_id == avis.id)
            .order_by(ContactAvisEnquete.id)
        )
        return list(self._session.execute(stmt).scalars())

    def eligible_contacts_for_avis(
        self, avis: AvisEnquete
    ) -> list[ContactAvisEnquete]:
        accepted = {StatutAvis.ACCEPTE, StatutAvis.ACCEPTE_RELATION_PRESSE}
        return [c for c in self.contacts_for_avis(avis) if c.status in accepted]

    def notify_from_avis(
        self,
        *,
        journalist: User,
        avis: AvisEnquete,
        article_url: str,
        article_title: str,
        article: Article | None = None,
        contacts: list[ContactAvisEnquete],
        message: str = "",
        opportunities_url_builder: UrlBuilder = _NO_URL,
    ) -> tuple[NotificationPublication, list[User]]:
        """Mode A : notify a selection of an avis's contacts."""
        # `AvisEnquete` exposes ownership via the standard `owner_id`
        # (via the Owned mixin) ; `journaliste_id` lives on
        # `ContactAvisEnquete`, not on the avis itself.
        if avis.owner_id != journalist.id:
            msg = (
                "Vous ne pouvez notifier qu'à partir d'un de vos "
                "avis d'enquête."
            )
            raise PublicationNotificationError(msg)
        own_ids = {c.id for c in self.contacts_for_avis(avis)}
        contacts = [c for c in contacts if c.id in own_ids]
        recipients = [c.expert for c in contacts if c.expert is not None]
        provenance = {c.expert_id: c.id for c in contacts}

        return self._dispatch(
            journalist=journalist,
            avis=avis,
            article=article,
            article_url=article_url,
            article_title=article_title,
            message=message,
            recipients=recipients,
            contact_provenance=provenance,
            opportunities_url_builder=opportunities_url_builder,
        )

    def notify_free_form(
        self,
        *,
        journalist: User,
        recipients: list[User],
        article_url: str,
        article_title: str,
        article: Article | None = None,
        message: str = "",
        opportunities_url_builder: UrlBuilder = _NO_URL,
    ) -> tuple[NotificationPublication, list[User]]:
        """Mode B : free-form recipient list. Inactive users are dropped."""
        recipients = [u for u in recipients if u is not None and u.active]
        return self._dispatch(
            journalist=journalist,
            avis=None,
            article=article,
            article_url=article_url,
            article_title=article_title,
            message=message,
            recipients=recipients,
            contact_provenance={},
            opportunities_url_builder=opportunities_url_builder,
        )

    # --------------------------------------------------------------
    # Internals
    # --------------------------------------------------------------

    def _dispatch(
        self,
        *,
        journalist: User,
        avis: AvisEnquete | None,
        article: Article | None,
        article_url: str,
        article_title: str,
        message: str,
        recipients: list[User],
        contact_provenance: dict[int, int],
        opportunities_url_builder: UrlBuilder,
    ) -> tuple[NotificationPublication, list[User]]:
        article_url = article_url.strip()
        article_title = article_title.strip()
        message = message.strip()
        if not article_url:
            msg = "L'URL de l'article est obligatoire."
            raise PublicationNotificationError(msg)

        # Deduplicate recipients + drop the sender themselves.
        unique: dict[int, User] = {}
        for u in recipients:
            if u.id == journalist.id:
                continue
            unique.setdefault(u.id, u)
        target_ids = list(unique.keys())

        # Batched anti-spam + anti-dedup pre-checks. Skipped in
        # debug mode so e2e tests can re-fire the same notification
        # without hitting the cap or the « same URL recently sent »
        # dedup.
        if _mail_debug_active():
            dup_ids: set[int] = set()
            capped_ids: set[int] = set()
        else:
            dup_ids = self._recent_dups(article_url, target_ids)
            capped_ids = self._over_cap(target_ids)
        accepted_users: list[User] = []
        skipped: list[User] = []
        for uid, user in unique.items():
            if uid in dup_ids or uid in capped_ids:
                skipped.append(user)
            else:
                accepted_users.append(user)

        now = datetime.now(UTC)
        notif = NotificationPublication(
            owner_id=journalist.id,
            avis_enquete_id=avis.id if avis is not None else None,
            article_id=article.id if article is not None else None,
            article_url=article_url,
            article_title=article_title,
            message=message,
            notified_at=now,
        )
        self._session.add(notif)
        self._session.flush()

        for user in accepted_users:
            self._session.add(
                NotificationPublicationContact(
                    notification_id=notif.id,
                    recipient_user_id=user.id,
                    contact_avis_enquete_id=contact_provenance.get(user.id),
                    sent_at=now,
                )
            )

        target_url = opportunities_url_builder(notif)
        in_app = container.get(NotificationService)
        for user in accepted_users:
            in_app.post(
                receiver=user,
                message=(
                    f"{journalist.full_name} vous a notifié de la "
                    f"publication de l'article « {article_title} »."
                ),
                url=target_url,
            )

        bw_name = resolve_user_bw_name(journalist, fallback="")
        for user in accepted_users:
            if not user.email:
                continue
            PublicationNotificationMail(
                sender="contact@aipress24.com",
                recipient=user.email,
                sender_mail=journalist.email or "",
                sender_full_name=journalist.full_name,
                sender_bw_name=bw_name,
                recipient_first_name=user.first_name or "",
                article_title=article_title,
                article_url=article_url,
                personal_message=message,
                opportunities_url=target_url,
            ).send()

        return notif, skipped

    def _recent_dups(
        self, article_url: str, recipient_ids: list[int]
    ) -> set[int]:
        """Recipients already notified for the same URL within the window."""
        if not recipient_ids:
            return set()
        since = datetime.now(UTC) - timedelta(days=DEDUP_WINDOW_DAYS)
        stmt = (
            select(NotificationPublicationContact.recipient_user_id)
            .join(
                NotificationPublication,
                NotificationPublicationContact.notification_id
                == NotificationPublication.id,
            )
            .where(
                NotificationPublicationContact.recipient_user_id.in_(
                    recipient_ids
                ),
                NotificationPublicationContact.sent_at >= since,
                NotificationPublication.article_url == article_url,
            )
        )
        return set(self._session.execute(stmt).scalars())

    def _over_cap(self, recipient_ids: list[int]) -> set[int]:
        """Recipients at/above the spam cap on the rolling window."""
        if not recipient_ids:
            return set()
        since = datetime.now(UTC) - timedelta(days=SPAM_WINDOW_DAYS)
        stmt = (
            select(
                NotificationPublicationContact.recipient_user_id,
                func.count().label("n"),
            )
            .where(
                NotificationPublicationContact.recipient_user_id.in_(
                    recipient_ids
                ),
                NotificationPublicationContact.sent_at >= since,
            )
            .group_by(NotificationPublicationContact.recipient_user_id)
        )
        return {
            row.recipient_user_id
            for row in self._session.execute(stmt)
            if row.n >= SPAM_CAP
        }


def _mail_debug_active() -> bool:
    """Local import — circular dep otherwise."""
    from app.flask.mail_debug import is_active

    return is_active()
