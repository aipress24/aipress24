# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Bug 0132: notify a media (BW owner) when a journalist proposes a sujet.

Mirrors the shape of `wip/services/pr_notifications.py` (which notifies a
client of a PR-agency publication on its behalf). Here the journalist
proposes a topic to a media: the media's BW owner — typically the rédacteur
en chef — should receive an email so the proposal doesn't sit unread."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.logging import warn
from app.services.emails import SujetPropositionNotificationMail

if TYPE_CHECKING:
    from app.models.auth import User
    from app.models.organisation import Organisation


def notify_media_of_sujet_proposition(
    *,
    author: User,
    media_org: Organisation,
    sujet_title: str,
    sujet_url: str,
) -> None:
    """Send an email to the target media's BW owner about a new sujet.

    Silently skipped when:
    - the author belongs to the same organisation as the media (a journalist
      proposing a topic to their own media: surfaces in their wall already);
    - the media has no resolvable BW-owner email.
    """
    author_org_id = getattr(author, "organisation_id", None)
    if author_org_id == media_org.id:
        return

    recipient_email = _pick_bw_owner_email(media_org)
    if not recipient_email:
        warn(
            f"No BW owner email for media {media_org.bw_name or media_org.name}; "
            "skipping sujet proposition notif"
        )
        return

    mail = SujetPropositionNotificationMail(
        sender="contact@aipress24.com",
        recipient=recipient_email,
        sender_mail=author.email,
        sender_full_name=author.full_name,
        media_name=media_org.bw_name or media_org.name,
        sujet_title=sujet_title,
        sujet_url=sujet_url,
    )
    mail.send()


def _pick_bw_owner_email(media_org: Organisation) -> str:
    """Resolve the BW owner email; fall back to first active member."""
    from app.modules.bw.bw_activation.user_utils import (
        get_active_business_wall_for_organisation,
    )

    bw = get_active_business_wall_for_organisation(media_org)
    if bw is not None and bw.owner_id:
        owner = _get_user_by_id(bw.owner_id)
        if owner and owner.email:
            return owner.email

    for member in getattr(media_org, "members", []):
        if getattr(member, "active", False) and member.email:
            return member.email
    return ""


def _get_user_by_id(user_id: int):
    from sqlalchemy import select

    from app.flask.extensions import db
    from app.models.auth import User

    return db.session.execute(
        select(User).where(User.id == user_id)
    ).scalar_one_or_none()
