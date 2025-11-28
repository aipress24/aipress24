# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask_login import current_user
from sqlalchemy import func, select

from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.services.emails import BWInvitationMail

from .utils import flush_session


def invite_users(mails: str | list[str], org_id: int) -> None:
    invitations_to_send = add_invited_users(mails, org_id)
    send_invitation_mails(invitations_to_send, org_id)


def add_invited_users(mails: str | list[str], org_id: int) -> list[str]:
    """Add user mails to the list of invited users, without sending mail.

    Note: This flushes but does NOT commit. The caller is responsible
    for committing at the request boundary.

    Returns: list of newly invited mails.
    """
    already_invited: list[str] = {
        m.lower() for m in emails_invited_to_organisation(org_id)
    }
    if isinstance(mails, str):
        mails = [mails]
    appended_mails: list[str] = []
    db_session = db.session
    for mail in mails:
        if not mail or "@" not in mail:
            continue
        if mail.lower() in already_invited:
            continue
        invitation = Invitation(email=mail, organisation_id=org_id)
        db_session.add(invitation)
        db_session.flush()
        already_invited.add(mail.lower())
        appended_mails.append(mail)
    flush_session(db_session)
    return appended_mails


def send_invitation_mails(mails: list[str], org_id: int) -> None:
    if not mails:
        return
    organisation = get_obj(org_id, Organisation)
    user = cast(User, current_user)
    sender_name = user.email
    bw_name = organisation.name

    for mail in mails:
        invit_mail = BWInvitationMail(
            sender="contact@aipress24.com",
            recipient=mail,
            sender_name=sender_name,
            bw_name=bw_name,
        )
        invit_mail.send()


def cancel_invitation_users(mails: str | list[str], org_id: int) -> None:
    """Cancel invitation for users.

    Note: This flushes but does NOT commit. The caller is responsible
    for committing at the request boundary.
    """
    if isinstance(mails, str):
        mails = [mails]
    db_session = db.session
    for mail in mails:
        if not mail or "@" not in mail:
            continue
        stmt = select(Invitation).where(
            func.lower(Invitation.email) == mail.lower(),
            Invitation.organisation_id == org_id,
        )
        found = db_session.scalar(stmt)
        if found:
            # This email is registered for this organisation
            db_session.delete(found)
            db_session.flush()
        db_session.flush()
    flush_session(db_session)


def emails_invited_to_organisation(org_id: int) -> list[str]:
    db_session = db.session
    stmt = select(Invitation).where(Invitation.organisation_id == org_id)
    return sorted({i.email for i in db_session.scalars(stmt)})
