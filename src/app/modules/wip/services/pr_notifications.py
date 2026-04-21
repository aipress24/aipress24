# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Notify a client when its PR agency publishes a contenu on its behalf."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flask import current_app

from app.logging import warn
from app.models.organisation import Organisation
from app.services.emails import PRPublicationNotificationMail

if TYPE_CHECKING:
    from app.models.auth import User


def notify_client_of_pr_publication(
    *,
    author: User,
    client_org: Organisation,
    content_type: str,
    content_title: str,
    content_url: str,
) -> None:
    """Send a one-off e-mail to the client BW owner if different from the author.

    Silently skipped when:
    - author belongs to the same organisation as client_org (not a PR agency
      publication scenario);
    - client_org has no `owner` relationship or no e-mail.
    """
    author_org_id = getattr(author, "organisation_id", None)
    if author_org_id == client_org.id:
        return

    recipient_email = _pick_bw_owner_email(client_org)
    if not recipient_email:
        warn(f"No BW owner email for {client_org.name}; skipping PR notif")
        return

    agency_org = getattr(author, "organisation", None)
    agency_name = agency_org.name if agency_org is not None else "Votre agence RP"

    mail = PRPublicationNotificationMail(
        sender="contact@aipress24.com",
        recipient=recipient_email,
        sender_mail=author.email,
        sender_full_name=author.full_name,
        agency_name=agency_name,
        client_name=client_org.name,
        content_type=content_type,
        content_title=content_title,
        content_url=content_url,
    )
    mail.send()


def _pick_bw_owner_email(client_org: Organisation) -> str:
    """Resolve the BW owner e-mail for this organisation.

    Falls back to the first active member's e-mail when the BW is missing
    or the owner is no longer reachable.
    """
    from app.modules.bw.bw_activation.user_utils import (
        get_active_business_wall_for_organisation,
    )

    bw = get_active_business_wall_for_organisation(client_org)
    if bw is not None and bw.owner_id:
        owner = _get_user_by_id(bw.owner_id)
        if owner and owner.email:
            return owner.email

    for member in getattr(client_org, "members", []):
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


def absolute_url_for(endpoint: str, **values) -> str:
    """Helper to build an absolute URL for the notification link."""
    from flask import url_for

    domain = str(current_app.config.get("SERVER_NAME") or "aipress24.com")
    protocol = "http" if domain.startswith("127.") else "https"
    path = url_for(endpoint, **values)
    return f"{protocol}://{domain}{path}"
