# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import func, select

from app.flask.extensions import db
from app.models.invitation import Invitation

from .utils import commit_session


def invite_users(mails: str | list[str], org_id: int) -> None:
    if isinstance(mails, str):
        mails = [mails]
    db_session = db.session
    for mail in mails:
        if not mail or "@" not in mail:
            continue
        stmt = select(Invitation).where(
            func.lower(Invitation.email) == mail.lower(),
        )
        found = db_session.scalar(stmt)
        if found and found.organisation_id == org_id:
            # This email is already registered for this organisation
            continue
            # allow a user to be invited by several organisations
            # db_session.delete(found)
            # db_session.flush()
        invitation = Invitation(email=mail, organisation_id=org_id)
        db_session.add(invitation)
        db_session.flush()
    commit_session(db_session)


def cancel_invitation_users(mails: str | list[str], org_id: int) -> None:
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
    commit_session(db_session)


def emails_invited_to_organisation(org_id: int) -> list[str]:
    db_session = db.session
    stmt = select(Invitation).where(Invitation.organisation_id == org_id)
    return sorted(i.email for i in db_session.scalars(stmt))
