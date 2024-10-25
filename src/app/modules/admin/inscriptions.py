# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import func, select

from app.flask.extensions import db
from app.models.preinscription import PreInscription

from .utils import commit_session


def register_users(mails: str | list[str], org_id: int) -> None:
    if isinstance(mails, str):
        mails = [mails]
    db_session = db.session
    for mail in mails:
        if not mail or "@" not in mail:
            continue
        stmt = select(PreInscription).where(
            func.lower(PreInscription.email) == mail.lower(),
        )
        found = db_session.scalar(stmt)
        if found:
            # This email is already registered for this organisation
            if found.organisation_id == org_id:
                continue
            db_session.delete(found)
            db_session.flush()
        pre_inscription = PreInscription(email=mail, organisation_id=org_id)
        db_session.add(pre_inscription)
        db_session.flush()
    commit_session(db_session)


def unregister_users(mails: str | list[str], org_id: int) -> None:
    if isinstance(mails, str):
        mails = [mails]
    db_session = db.session
    for mail in mails:
        if not mail or "@" not in mail:
            continue
        stmt = select(PreInscription).where(
            func.lower(PreInscription.email) == mail.lower(),
            PreInscription.organisation_id == org_id,
        )
        found = db_session.scalar(stmt)
        if found:
            # This email is already registered for this organisation
            db_session.delete(found)
            db_session.flush()
        db_session.flush()
    commit_session(db_session)


def registered_organisation(mail: str) -> int | None:
    if not mail or "@" not in mail:
        return None
    db_session = db.session
    stmt = select(PreInscription).where(
        func.lower(PreInscription.email) == mail.lower()
    )
    return db_session.scalar(stmt)


def mails_registered_for_organisation(org_id: int) -> list[str]:
    db_session = db.session
    stmt = select(PreInscription).where(
        func.lower(PreInscription.organisation_id) == org_id
    )
    return sorted(p.email for p in db_session.scalars(stmt))
