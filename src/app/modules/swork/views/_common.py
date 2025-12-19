# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared components for swork views."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import sqlalchemy as sa
from attr import define
from flask import g

from app.flask.extensions import db
from app.flask.lib.view_model import ViewModel
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.swork.models import Group, group_members_table
from app.modules.wire.models import ArticlePost

# Lazy import to avoid circular import
# from app.services.social_graph import adapt

if TYPE_CHECKING:
    from app.modules.swork.pages.masked_fields import MaskFields


def get_menus() -> dict:
    """Get menus dict for template context.

    Returns:
        Dict with 'secondary' key containing menu items
    """
    from app.modules.swork.settings import SWORK_MENU
    from app.services.menus import make_menu

    return {"secondary": make_menu(SWORK_MENU)}


# Member page tabs
MEMBER_TABS = [
    {"id": "profile", "label": "Profil"},
    {"id": "publications", "label": "Publications"},
    {"id": "activities", "label": "Activités"},
    {"id": "groups", "label": "Groupes"},
    {"id": "followees", "label": "Abonnements"},
    {"id": "followers", "label": "Abonnés"},
]

# Group page tabs
GROUP_TABS = [
    {"id": "wall", "label": "Wall"},
    {"id": "description", "label": "Description"},
    {"id": "members", "label": "Membres"},
]

# Fields that can be masked based on contact type
MASK_FIELDS = {
    "email": "email",
    "mobile": "tel_mobile",
    "email_relation_presse": "email_relation_presse",
}


@define
class PostVM(ViewModel):
    """ViewModel for ArticlePost."""

    def extra_attrs(self):
        article = cast("ArticlePost", self._model)

        if article.published_at:
            age = article.published_at.humanize(locale="fr")
        else:
            age = "(not set)"

        return {
            "author": UserVM(article.owner),
            "age": age,
            "summary": article.subheader,
            "likes": article.like_count,
            "replies": article.comment_count,
            "views": article.view_count,
        }


@define
class UserVM(ViewModel):
    """ViewModel for User."""

    @property
    def user(self):
        return cast("User", self._model)

    def get_banner_url(self) -> str:
        return self.user.cover_image_signed_url()

    def extra_attrs(self):
        from app.services.social_graph import adapt

        user = self.user

        return {
            "name": user.full_name,
            "job_title": user.job_title,
            "organisation_name": user.organisation_name,
            "image_url": user.photo_image_signed_url(),
            "is_following": adapt(g.user).is_following(user),
            "followers": self.get_followers(),
            "followees": self.get_followees(),
            "posts": self.get_posts(),
            "groups": self.get_groups(),
            "banner_url": self.get_banner_url(),
        }

    def get_groups(self) -> list[Group]:
        c = group_members_table.c
        stmt1 = sa.select(c.group_id).where(c.user_id == self.user.id)
        ids = db.session.scalars(stmt1)

        stmt2 = (
            sa.select(Group)
            .where(Group.id.in_(ids))
            .where(Group.privacy == "public")
            .order_by(Group.name)
        )
        return list(db.session.scalars(stmt2))

    def get_followers(self, limit: int | None = None) -> list[UserVM]:
        from app.services.social_graph import adapt

        followers: list[User] = adapt(self.user).get_followers(
            order_by=-User.karma, limit=limit
        )
        return UserVM.from_many(followers)

    def get_followees(self, limit: int | None = None) -> list[UserVM]:
        from app.services.social_graph import adapt

        followees: list[User] = adapt(self.user).get_followees(
            order_by=-User.karma, limit=limit
        )
        return UserVM.from_many(followees)

    def get_posts(self) -> list[PostVM]:
        posts = (
            db.session.query(ArticlePost)
            .filter(ArticlePost.owner_id == self.user.id)
            .filter(ArticlePost.status == PublicationStatus.PUBLIC)
            .order_by(ArticlePost.published_at.desc())
            .all()
        )
        return PostVM.from_many(posts)


def filter_email_mobile(user: User, target_user: User) -> MaskFields:
    """Return list of field names to be masked according to the logged user contact type.

    "contact_type" of the logged user can be from PRESSE to ETUDIANT.
    If this method does not find a mode (email) in the permitted list,
    the mode *may* be still allowed as FOLLOWEE contact type, in a later stage.
    """
    from app.modules.swork.pages.masked_fields import MaskFields
    from app.services.social_graph import SocialUser, adapt

    mask_fields = MaskFields()
    contact_type = user.profile.contact_type
    user_allow = target_user.profile.show_contact_details

    for mode, field in MASK_FIELDS.items():
        key = f"{mode}_{contact_type}"
        if not user_allow.get(key):
            mask_fields.add_field(field)
            mask_fields.add_message(f"{mode} not allowed for {contact_type}")

    # Check followee permissions
    if not mask_fields.masked:
        mask_fields.add_message("no field masked")
        return mask_fields

    member_is_follower = None
    for mode in ("email", "mobile"):
        if MASK_FIELDS[mode] not in mask_fields.masked:
            mask_fields.add_message(f"{mode} already allowed")
            continue
        key_mode = f"{mode}_FOLLOWEE"
        if not user_allow.get(key_mode):
            mask_fields.add_message(f"{mode}: followees not allowed")
            continue
        if member_is_follower is None:
            member_user: SocialUser = adapt(target_user)
            member_is_follower = member_user.is_following(user)
        if not member_is_follower:
            mask_fields.add_message(f"{mode}: member is not a follower")
            continue
        mask_fields.remove_field(MASK_FIELDS[mode])
        mask_fields.add_message(f"{mode}: allowed because followee")

    return mask_fields


def is_group_member(user: User, group: Group) -> bool:
    """Check if user is a member of the group."""
    table = group_members_table
    c = table.c
    stmt = sa.select(table).where(c.user_id == user.id, c.group_id == group.id)
    rows = db.session.execute(stmt)
    return len(list(rows)) == 1


def join_group(user: User, group: Group) -> None:
    """Add user to group."""
    from app.services.activity_stream import post_activity

    table = group_members_table
    stmt = sa.insert(table).values(user_id=user.id, group_id=group.id)
    db.session.execute(stmt)
    post_activity("Join", user, group)


def leave_group(user: User, group: Group) -> None:
    """Remove user from group."""
    from app.services.activity_stream import post_activity

    table = group_members_table
    c = table.c
    stmt = sa.delete(table).where(c.user_id == user.id, c.group_id == group.id)
    db.session.execute(stmt)
    post_activity("Leave", user, group)
