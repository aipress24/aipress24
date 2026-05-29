# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.organisation import Organisation
from app.services.roles import add_role

from .invitations import (
    cancel_invitation_users,
    emails_invited_to_organisation,
    invite_users,
)
from .utils import get_user_per_email, remove_user_organisation, set_user_organisation


def remove_members_emails(org: Organisation, mails_to_remove: set[str]) -> None:
    """Remove members from organisation by emails."""
    for member in org.members:
        if member.email.lower() in mails_to_remove:
            remove_user_organisation(member)


def add_members_emails(org: Organisation, mails_to_add: set[str]) -> None:
    """Add members to organisation by emails."""
    for mail in mails_to_add:
        user = get_user_per_email(mail)
        if not user:
            continue
        set_user_organisation(user, org)


def change_members_emails(
    org: Organisation,
    raw_mails: str,
    remove_only: bool = False,
    never_remove: str | list[str] | None = None,
) -> None:
    """Update organisation members by emails."""
    updated_mails = set(raw_mails.lower().split())

    if never_remove:
        if isinstance(never_remove, str):
            never_remove = [never_remove]
        keep_mails: set[str] = {m.lower() for m in never_remove}
    else:
        keep_mails = set()

    current_emails: set[str] = {u.email.lower() for u in org.members}

    mails_to_remove = {
        m for m in current_emails if m not in updated_mails and m not in keep_mails
    }
    remove_members_emails(org, mails_to_remove)

    if remove_only:
        return

    mails_to_add = {m for m in updated_mails if m not in current_emails}
    add_members_emails(org, mails_to_add)


def add_managers_emails(org: Organisation, mails: str | list[str]) -> None:
    """Add managers to an organisation based on email list.

    Note: This flushes but does NOT commit. The caller is responsible
    for committing at the request boundary.
    """
    if isinstance(mails, str):
        mails = [mails]
    new_mails = {m.lower().strip() for m in mails}
    db_session = db.session
    current_managers = [u for u in org.members if u.has_role(RoleEnum.MANAGER)]
    current_members_emails = {u.email.lower() for u in org.members}
    current_managers_emails = {u.email.lower() for u in current_managers}
    # add users of the new list that are not in the current list of members
    for mail in new_mails:
        if mail not in current_managers_emails:
            if mail not in current_members_emails:
                continue  # require manager to be already member
            user = get_user_per_email(mail)
            if not user:
                continue
            add_role(user, RoleEnum.MANAGER)
            db_session.merge(user)
            db_session.flush()


def change_invitations_emails(org: Organisation, raw_mails: str) -> None:
    new_mails = list(set(raw_mails.split()))  # keep mail case
    new_mails_lower = {m.lower() for m in new_mails}
    current_invitations = emails_invited_to_organisation(org.id)
    canceled = [m for m in current_invitations if m.lower() not in new_mails_lower]
    cancel_invitation_users(canceled, org.id)
    if new_mails:
        invite_users(new_mails, org.id)
