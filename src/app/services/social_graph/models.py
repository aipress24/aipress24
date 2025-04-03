# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa

from app.models.auth import User
from app.models.base import Base
from app.models.base_content import BaseContent
from app.models.organisation import Organisation

#
# Tables for many-to-many relationships
#
following_users_table = sa.Table(
    "soc_following_users",
    Base.metadata,
    sa.Column(
        "follower_id",
        sa.Integer,
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column(
        "followee_id",
        sa.Integer,
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.UniqueConstraint("follower_id", "followee_id"),
)

following_orgs_table = sa.Table(
    "soc_following_orgs",
    Base.metadata,
    sa.Column(
        "follower_id",
        sa.Integer,
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column(
        "followee_id",
        sa.BigInteger,
        sa.ForeignKey(Organisation.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.UniqueConstraint("follower_id", "followee_id"),
)

likes_table = sa.Table(
    "soc_likes",
    Base.metadata,
    sa.Column(
        "user_id",
        sa.Integer,
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column(
        "content_id",
        sa.BigInteger,
        sa.ForeignKey(BaseContent.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.UniqueConstraint("user_id", "content_id"),
)
