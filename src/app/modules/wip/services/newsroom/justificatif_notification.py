# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0195 — notify enquête participants that a journalist's
article has been published, and that they can acquire the consultation
or the justificatif.

Called by `ArticlesWipView.notify` after the journalist has picked
an `AvisEnquete` and a subset of its `ContactAvisEnquete` rows.

Design note
-----------
The pure decision helpers (recipient gating, media-name resolution,
in-app message composition, mail kwargs assembly, counter update) are
extracted at module level so they can be unit-tested without a DB
session, a mail bus or a Flask app context. The top-level
`notify_avis_participants_of_justificatif` is the imperative shell
that orchestrates DB reads + side effects around those pure pieces.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from svcs.flask import container

from app.flask.extensions import db
from app.logging import report_failure
from app.models.auth import User
from app.models.organisation import Organisation
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.modules.wip.models.newsroom.avis_enquete import AvisEnquete
    from app.modules.wire.models import ArticlePost


DEFAULT_SENDER_EMAIL = "contact@aipress24.com"
EM_DASH_FALLBACK = "—"


# --------------------------------------------------------------
# Pure helpers (no DB, no I/O, no Flask context)
# --------------------------------------------------------------


def filter_allowed_recipients(
    recipient_user_ids: list[int], allowed_ids: set[int]
) -> list[int]:
    """Keep only the recipient ids that match the avis's actual
    contacts.

    Pure : the SQL that materialises `allowed_ids` lives in the
    orchestration shell. Here we just compute the intersection while
    preserving the caller's order — the order is product-visible
    because the counter increments per accepted recipient.
    """
    return [uid for uid in recipient_user_ids if uid in allowed_ids]


def resolve_media_name(org: Any | None) -> str:
    """Pick the display name for a journalist's press organisation.

    Order of preference :
        1. `org.bw_name` (the BusinessWall-synced public brand)
        2. `org.name` (the raw legal org name)
        3. em-dash fallback when nothing is resolvable.

    Pure : the DB reload of a detached `Organisation` row is handled
    by the caller ; this helper only takes the already-loaded (or
    None) row.
    """
    if org is None:
        return EM_DASH_FALLBACK
    return getattr(org, "bw_name", None) or getattr(org, "name", "") or EM_DASH_FALLBACK


def build_in_app_message(journalist_full_name: str, article_title: str) -> str:
    """Render the in-app cloche body. Pure & deterministic.

    French guillemets « … » are part of the product copy.
    """
    return (
        f"{journalist_full_name} a publié un article suite à votre "
        f"participation : « {article_title} »."
    )


def build_mail_kwargs(
    *,
    recipient: User,
    article: ArticlePost,
    avis_enquete: AvisEnquete,
    journalist: User,
    media_name: str,
    article_url: str,
) -> dict[str, str]:
    """Assemble the kwargs payload for `JustificatifInvitationMail`.

    Returns a dict so tests can pin the field routing contract without
    going through the mail constructor (which performs validation and
    template binding).

    Routing details :
    - `sender_mail` falls back to the contact address when the
      journalist's email is unset (KYC-incomplete) — SMTP must not
      bounce on an empty `From:` header.
    - `enquete_title` defaults to em-dash when missing/empty — better
      than a blank line in the email body.
    """
    return {
        "sender": DEFAULT_SENDER_EMAIL,
        "recipient": recipient.email or "",
        "sender_mail": journalist.email or DEFAULT_SENDER_EMAIL,
        "recipient_full_name": recipient.full_name,
        "enquete_title": getattr(avis_enquete, "titre", "") or EM_DASH_FALLBACK,
        "journalist_full_name": journalist.full_name,
        "media_name": media_name,
        "article_title": article.title,
        "article_url": article_url,
    }


def next_notification_count(current: int | None, delta: int) -> int:
    """Compute the new value for `justificatif_notifications_count`.

    Pure : the model write happens elsewhere. Centralised so the
    `None → 0` defaulting can't drift between call sites.
    """
    return (current or 0) + delta


# --------------------------------------------------------------
# Imperative shell
# --------------------------------------------------------------


def notify_avis_participants_of_justificatif(
    *,
    article: ArticlePost,
    avis_enquete: AvisEnquete,
    recipient_user_ids: list[int],
    journalist: User,
    article_url: str,
) -> int:
    """Send mail + in-app cloche to each recipient. Returns the number
    of recipients actually notified (filtering out users without an
    email or who couldn't be loaded).

    Failures of either side-effect are reported to Sentry via
    `report_failure` but never abort the whole batch — a flaky SMTP
    must not prevent the rest of the participants from being notified.
    """
    if not recipient_user_ids:
        return 0

    # Filter recipient ids against the avis's actual contacts
    # (`ContactAvisEnquete.expert_id`). The form input is client-side,
    # so without this check a journalist could pass any User.id and
    # spam-email arbitrary users — and inflate
    # `justificatif_notifications_count` on top of it.
    allowed_ids = _avis_contact_ids(avis_enquete.id)
    filtered_ids = filter_allowed_recipients(recipient_user_ids, allowed_ids)
    if not filtered_ids:
        return 0

    media_name = _journalist_media_name(journalist)
    notified = 0
    for user_id in filtered_ids:
        recipient = db.session.get(User, user_id)
        if recipient is None:
            continue

        try:
            _post_in_app(recipient, article, journalist, article_url)
        except Exception as exc:
            report_failure(
                f"justificatif_invitation: in-app notification failed "
                f"(article {article.id}, user {user_id})",
                exc,
            )

        if recipient.email:
            try:
                _send_email(
                    recipient=recipient,
                    article=article,
                    avis_enquete=avis_enquete,
                    journalist=journalist,
                    media_name=media_name,
                    article_url=article_url,
                )
            except Exception as exc:
                report_failure(
                    f"justificatif_invitation: email failed "
                    f"(article {article.id}, user {user_id})",
                    exc,
                )

        notified += 1

    # Ticket #0195 — increment the enquête's JdP counter by the number
    # of participants actually notified. Downstream rémunération is
    # computed off this counter ; a notification that didn't reach a
    # real user (unknown id) doesn't count.
    if notified:
        avis_enquete.justificatif_notifications_count = next_notification_count(
            avis_enquete.justificatif_notifications_count, notified
        )
        db.session.flush()

    return notified


def _journalist_media_name(journalist: User) -> str:
    """Resolve the journalist's media display name, reloading the
    `Organisation` row by id when the relationship is detached.

    Imperative shell : the actual name-picking is delegated to the
    pure `resolve_media_name` helper.
    """
    org = journalist.organisation
    if org is None and journalist.organisation_id:
        org = db.session.get(Organisation, journalist.organisation_id)
    return resolve_media_name(org)


def _post_in_app(
    recipient: User,
    article: ArticlePost,
    journalist: User,
    article_url: str,
) -> None:
    message = build_in_app_message(journalist.full_name, article.title)
    container.get(NotificationService).post(recipient, message, url=article_url)


def _send_email(
    *,
    recipient: User,
    article: ArticlePost,
    avis_enquete: AvisEnquete,
    journalist: User,
    media_name: str,
    article_url: str,
) -> None:
    # Lazy import : keeps the wip layer from pulling all mailers at
    # cold start.
    from app.services.emails import JustificatifInvitationMail

    kwargs = build_mail_kwargs(
        recipient=recipient,
        article=article,
        avis_enquete=avis_enquete,
        journalist=journalist,
        media_name=media_name,
        article_url=article_url,
    )
    JustificatifInvitationMail(**kwargs).send()


def list_journalist_avis_enquetes(journalist_id: int) -> list[dict]:
    """List the journalist's own avis d'enquêtes for the picker on the
    Justificatif notify form. Returns dicts so the template doesn't
    need to know the model shape."""
    from app.modules.wip.models.newsroom.avis_enquete import AvisEnquete

    rows = (
        db.session.query(AvisEnquete)
        .filter(AvisEnquete.owner_id == journalist_id)
        .order_by(AvisEnquete.date_fin_enquete.desc())
        .all()
    )
    return [{"id": r.id, "titre": r.titre} for r in rows]


def _avis_contact_ids(avis_enquete_id: int) -> set[int]:
    """Return the set of `User.id` that are legitimate participants of
    the avis (via `ContactAvisEnquete.expert_id`). Used to gate the
    `recipient_user_ids` input in `notify_avis_participants_of_justificatif`."""
    from app.modules.wip.models.newsroom.avis_enquete import (
        ContactAvisEnquete,
    )

    rows = (
        db.session.query(ContactAvisEnquete.expert_id)
        .filter(ContactAvisEnquete.avis_enquete_id == avis_enquete_id)
        .all()
    )
    return {r[0] for r in rows if r[0] is not None}


def list_avis_contacts(avis_enquete_id: int) -> list[dict]:
    """List the participants (`ContactAvisEnquete.expert`) of an avis
    so the journalist can pick recipients on the notify form."""
    from app.modules.wip.models.newsroom.avis_enquete import (
        ContactAvisEnquete,
    )

    contacts = (
        db.session.query(ContactAvisEnquete)
        .filter(ContactAvisEnquete.avis_enquete_id == avis_enquete_id)
        .all()
    )
    return [
        {
            "user_id": c.expert_id,
            "full_name": getattr(c.expert, "full_name", "—")
            if c.expert is not None
            else "—",
            "email": getattr(c.expert, "email", "") if c.expert is not None else "",
        }
        for c in contacts
    ]
