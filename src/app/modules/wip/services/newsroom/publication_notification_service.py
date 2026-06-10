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

Design note
-----------
Pure decision helpers (input normalisation, recipient deduplication,
eligibility predicate, in-app message composition, mail kwargs
assembly) are extracted at module level so they can be unit-tested
without a DB session or mail bus. The `PublicationNotificationService`
class is the imperative shell that orchestrates DB writes + email
dispatch around those pure pieces.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
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

ACCEPTED_STATUSES: frozenset[StatutAvis] = frozenset(
    {StatutAvis.ACCEPTE, StatutAvis.ACCEPTE_RELATION_PRESSE}
)

UrlBuilder = Callable[[NotificationPublication], str]
_NO_URL: UrlBuilder = lambda _n: ""  # noqa: E731


class PublicationNotificationError(ValueError):
    """User-facing validation error (empty URL, ownership violation)."""


# --------------------------------------------------------------
# Pure helpers (no DB, no I/O)
# --------------------------------------------------------------


def is_eligible_contact(contact: ContactAvisEnquete) -> bool:
    """True iff a contact has accepted the avis (mode A pre-check)."""
    return contact.status in ACCEPTED_STATUSES


def normalise_inputs(
    article_url: str, article_title: str, message: str
) -> tuple[str, str, str]:
    """Strip the three user-supplied free-text fields.

    Centralised so the validation, persistence and mail rendering
    code paths all agree on whitespace handling.
    """
    return article_url.strip(), article_title.strip(), message.strip()


def validate_article_url(article_url: str) -> None:
    """Raise `PublicationNotificationError` if the URL is empty."""
    if not article_url:
        msg = "L'URL de l'article est obligatoire."
        raise PublicationNotificationError(msg)


def deduplicate_recipients(
    recipients: Iterable[User], sender_id: int
) -> dict[int, User]:
    """Order-preserving recipient dedup, drops the sender themselves.

    Returns an `{id: user}` dict so callers can both iterate in order
    and look up by id (e.g. for the contact-provenance map).
    """
    unique: dict[int, User] = {}
    for u in recipients:
        user_id = int(u.id)
        if user_id == sender_id:
            continue
        unique.setdefault(user_id, u)
    return unique


def partition_recipients(
    unique: dict[int, User],
    *,
    dup_ids: set[int],
    capped_ids: set[int],
) -> tuple[list[User], list[User]]:
    """Split unique recipients into (accepted, skipped) by dup/cap sets.

    Pure : the SQL is performed elsewhere ; here we just apply two
    pre-computed exclusion sets and preserve insertion order.
    """
    accepted: list[User] = []
    skipped: list[User] = []
    for uid, user in unique.items():
        if uid in dup_ids or uid in capped_ids:
            skipped.append(user)
        else:
            accepted.append(user)
    return accepted, skipped


def filter_own_contacts(
    contacts: list[ContactAvisEnquete], own_ids: set[int]
) -> list[ContactAvisEnquete]:
    """Drop any contact whose id is not in the avis's own contact set.

    Defence in depth : the form POST might smuggle a `contact_id` for
    a contact attached to a *different* avis.
    """
    return [c for c in contacts if c.id in own_ids]


def extract_recipients_and_provenance(
    contacts: Iterable[ContactAvisEnquete],
) -> tuple[list[User], dict[int, int]]:
    """From a list of contacts, derive (recipients, provenance map).

    `provenance` maps `expert_id -> contact_id` so that the
    `NotificationPublicationContact` row can record which contact
    originated the notification (audit trail for mode A).
    """
    recipients = [c.expert for c in contacts if c.expert is not None]
    provenance = {c.expert_id: c.id for c in contacts}
    return recipients, provenance


def filter_active_users(users: Iterable[User | None]) -> list[User]:
    """Mode B input scrubber : drop None entries and inactive users."""
    return [u for u in users if u is not None and u.active]


def build_in_app_message(sender_full_name: str, article_title: str) -> str:
    """Render the in-app notification body. Pure & deterministic."""
    return (
        f"{sender_full_name} vous a notifié de la "
        f"publication de l'article « {article_title} »."
    )


def build_mail_kwargs(
    *,
    sender: User,
    sender_bw_name: str,
    recipient: User,
    article_title: str,
    article_url: str,
    message: str,
    opportunities_url: str,
) -> dict[str, str]:
    """Assemble the kwargs payload for `PublicationNotificationMail`.

    Returns a dict so tests can pin the contract without going through
    the mail constructor (which has side effects).
    """
    return {
        "sender": "contact@aipress24.com",
        "recipient": recipient.email or "",
        "sender_mail": sender.email or "",
        "sender_full_name": sender.full_name,
        "sender_bw_name": sender_bw_name,
        "recipient_first_name": recipient.first_name or "",
        "article_title": article_title,
        "article_url": article_url,
        "personal_message": message,
        "opportunities_url": opportunities_url,
    }


# --------------------------------------------------------------
# Imperative shell
# --------------------------------------------------------------


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

    def eligible_contacts_for_avis(self, avis: AvisEnquete) -> list[ContactAvisEnquete]:
        return [c for c in self.contacts_for_avis(avis) if is_eligible_contact(c)]

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
            msg = "Vous ne pouvez notifier qu'à partir d'un de vos avis d'enquête."
            raise PublicationNotificationError(msg)
        own_ids = {c.id for c in self.contacts_for_avis(avis)}
        contacts = filter_own_contacts(contacts, own_ids)
        recipients, provenance = extract_recipients_and_provenance(contacts)

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
        recipients = filter_active_users(recipients)
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
        article_url, article_title, message = normalise_inputs(
            article_url, article_title, message
        )
        validate_article_url(article_url)

        unique = deduplicate_recipients(recipients, journalist.id)
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
        accepted_users, skipped = partition_recipients(
            unique, dup_ids=dup_ids, capped_ids=capped_ids
        )

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
        in_app_message = build_in_app_message(journalist.full_name, article_title)
        for user in accepted_users:
            in_app.post(
                receiver=user,
                message=in_app_message,
                url=target_url,
            )

        bw_name = resolve_user_bw_name(journalist, fallback="")
        for user in accepted_users:
            if not user.email:
                continue
            kwargs = build_mail_kwargs(
                sender=journalist,
                sender_bw_name=bw_name,
                recipient=user,
                article_title=article_title,
                article_url=article_url,
                message=message,
                opportunities_url=target_url,
            )
            PublicationNotificationMail(**kwargs).send()

        return notif, skipped

    def _recent_dups(self, article_url: str, recipient_ids: list[int]) -> set[int]:
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
                NotificationPublicationContact.recipient_user_id.in_(recipient_ids),
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
                NotificationPublicationContact.recipient_user_id.in_(recipient_ids),
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
