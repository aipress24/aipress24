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


def change_members_emails(
    org: Organisation,
    raw_mails: str,
    remove_only: bool = False,
    never_remove: str | list[str] | None = None,
) -> None:
    new_mails = set(raw_mails.lower().split())
    if never_remove:
        if isinstance(never_remove, str):
            never_remove = [never_remove]
        keep_mails: set[str] = {m.lower() for m in never_remove}
    else:
        keep_mails = set()

    current_emails = {u.email.lower() for u in org.members}
    # remove users that are not in the new list of members
    for member in org.members:
        if member.email not in new_mails and member.email not in keep_mails:
            remove_user_organisation(member)
    if remove_only:
        return
    # add users of the new list that are not in the current list of members
    for mail in new_mails:
        if mail not in current_emails:
            user = get_user_per_email(mail)
            if not user:
                continue
            set_user_organisation(user, org)


def change_managers_emails(
    org: Organisation, raw_mails: str, keep_one: bool = False
) -> None:
    """Update the managers of an organisation based on email list.

    Note: This flushes but does NOT commit. The caller is responsible
    for committing at the request boundary.
    """
    new_mails = set(raw_mails.lower().split())
    db_session = db.session
    current_managers = [u for u in org.members if u.is_manager]
    current_members_emails = {u.email.lower() for u in org.members}
    current_managers_emails = {u.email.lower() for u in current_managers}
    some_new_manager = False
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
            some_new_manager = True
    if keep_one and not some_new_manager:
        # - option "keep_one" active (thus managing the organisation from
        #   the BW admin page)
        # - No new manager was added
        # => do not allow to remove the last manager email
        removable_count = len(current_managers) - 1
    else:
        # either "keep_one" is not active (site admin management) or some
        # new manager was added
        # => allow to remove all previous managers
        removable_count = len(current_managers)
    # remove managers that are not in the new list of managers
    for manager in current_managers:
        if manager.email not in new_mails and removable_count > 0:
            manager.remove_role(RoleEnum.MANAGER)
            db_session.merge(manager)
            db_session.flush()
            removable_count -= 1


def add_managers_emails(org: Organisation, mails: str | list[str]) -> None:
    """Add managers to an organisation based on email list.

    Note: This flushes but does NOT commit. The caller is responsible
    for committing at the request boundary.
    """
    if isinstance(mails, str):
        mails = [mails]
    new_mails = {m.lower().strip() for m in mails}
    db_session = db.session
    current_managers = [u for u in org.members if u.is_manager]
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


def change_leaders_emails(org: Organisation, raw_mails: str) -> None:
    """Update the leaders of an organisation based on email list.

    Note: This flushes but does NOT commit. The caller is responsible
    for committing at the request boundary.
    """
    new_mails = set(raw_mails.lower().split())
    db_session = db.session
    current_leaders = [u for u in org.members if u.is_leader]
    current_members_emails = {u.email.lower() for u in org.members}
    current_leaders_emails = {u.email.lower() for u in current_leaders}
    # remove leaders that are not in the new list of leaders
    for leader in current_leaders:
        if leader.email not in new_mails:
            leader.remove_role(RoleEnum.LEADER)
            db_session.merge(leader)
            db_session.flush()
    # add users of the new list that are not in the current list of members
    for mail in new_mails:
        if mail not in current_leaders_emails:
            if mail not in current_members_emails:
                continue  # require leader to be already member
            user = get_user_per_email(mail)
            if not user:
                continue
            add_role(user, RoleEnum.LEADER)
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
