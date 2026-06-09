# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0195 — notify enquête participants that a journalist's
article has been published, and that they can acquire the consultation
or the justificatif.

Called by `ArticlesWipView.notify` after the journalist has picked
an `AvisEnquete` and a subset of its `ContactAvisEnquete` rows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.flask.extensions import db
from app.logging import report_failure
from app.models.auth import User
from app.models.organisation import Organisation
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.modules.wip.models.newsroom.avis_enquete import AvisEnquete
    from app.modules.wire.models import ArticlePost


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

    media_name = _journalist_media_name(journalist)
    notified = 0
    for user_id in recipient_user_ids:
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
    #
    # We flush rather than commit : the web request commits at its
    # boundary, and tests' transactional wrapper rolls back. Hard-
    # committing here would leak rows across test isolation.
    if notified:
        current = avis_enquete.justificatif_notifications_count or 0
        avis_enquete.justificatif_notifications_count = current + notified
        db.session.flush()

    return notified


def _journalist_media_name(journalist: User) -> str:
    org = journalist.organisation
    if org is None and journalist.organisation_id:
        org = db.session.get(Organisation, journalist.organisation_id)
    if org is None:
        return "—"
    return getattr(org, "bw_name", None) or getattr(org, "name", "") or "—"


def _post_in_app(
    recipient: User,
    article: ArticlePost,
    journalist: User,
    article_url: str,
) -> None:
    message = (
        f"{journalist.full_name} a publié un article suite à votre "
        f"participation : « {article.title} »."
    )
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

    mail = JustificatifInvitationMail(
        sender="contact@aipress24.com",
        recipient=recipient.email,
        sender_mail=journalist.email or "contact@aipress24.com",
        recipient_full_name=recipient.full_name,
        enquete_title=getattr(avis_enquete, "titre", "") or "—",
        journalist_full_name=journalist.full_name,
        media_name=media_name,
        article_title=article.title,
        article_url=article_url,
    )
    mail.send()


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
