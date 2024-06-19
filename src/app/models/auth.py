# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import typing
import uuid

import sqlalchemy as sa
from aenum import StrEnum
from flask_security import RoleMixin, UserMixin
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base
from .geoloc import GeoLocation

# from app.services.security import check_password_hash, generate_password_hash
from .mixins import Addressable

if typing.TYPE_CHECKING:
    from .orgs import Organisation


class RoleEnum(StrEnum):
    ADMIN = "admin"
    GUEST = "guest"

    PRESS_MEDIA = "journalist"
    PRESS_RELATIONS = "press_relations"
    EXPERT = "expert"
    ACADEMIC = "academic"
    TRANSFORMER = "transformer"


class CommunityEnum(StrEnum):
    PRESS_MEDIA = "Press & Media"
    COMMUNICANTS = "Communicants"
    LEADERS_EXPERTS = "Leaders & Experts"
    TRANSFORMERS = "Transformers"
    ACADEMICS = "Academics"


roles_users = sa.Table(
    "aut_roles_users",
    Base.metadata,
    sa.Column(
        "user_id",
        sa.Integer,
        sa.ForeignKey("aut_user.id", name="fk_aut_roles_users_user_id"),
    ),
    sa.Column(
        "role_id",
        sa.Integer,
        sa.ForeignKey("aut_role.id", name="fk_aut_roles_users_role_id"),
    ),
)


class User(Addressable, UserMixin, Base):
    __tablename__ = "aut_user"

    id: Mapped[int] = mapped_column(primary_key=True)

    # username: Mapped[str] = mapped_column(index=True, unique=True)
    email: Mapped[str] = mapped_column(unique=True)
    password: Mapped[str | None] = mapped_column(sa.String(64))
    _password_hash: Mapped[str | None] = mapped_column(sa.String(64))

    # Flask Security
    active: Mapped[bool] = mapped_column(default=False)
    fs_uniquifier: Mapped[str] = mapped_column(sa.String(64), unique=True)

    community_primary: Mapped[CommunityEnum] = mapped_column(
        sa.Enum(CommunityEnum), default=CommunityEnum.PRESS_MEDIA
    )
    community_secondary: Mapped[CommunityEnum | None] = mapped_column(
        sa.Enum(CommunityEnum), nullable=True
    )

    gender: Mapped[str] = mapped_column(sa.Unicode(1), default="?")
    first_name: Mapped[str] = mapped_column(sa.Unicode(64), default="")
    last_name: Mapped[str] = mapped_column(sa.Unicode(64), default="")

    job_title: Mapped[str] = mapped_column(default="")
    job_description: Mapped[str] = mapped_column(default="")
    bio: Mapped[str] = mapped_column(default="")
    education: Mapped[str] = mapped_column(default="")
    hobbies: Mapped[str] = mapped_column(default="")

    organisation_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("crp_organisation.id", name="fk_aut_user_org_id")
    )
    organisation_name: Mapped[str] = mapped_column(default="")

    # TODO
    # geoloc_id = sa.Column(sa.Integer, sa.ForeignKey("geo_loc.id"), nullable=True)
    geoloc_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("geo_loc.id")
    )
    geoloc = relationship(GeoLocation)

    # TODO: use content repository
    profile_image_url: Mapped[str] = mapped_column(default="")
    cover_image_url: Mapped[str] = mapped_column(default="")

    status: Mapped[str] = mapped_column(default="Débutant")

    #: Reputation points
    karma: Mapped[float] = mapped_column(default=0.0)

    # Relationships
    organisation: Mapped[Organisation] = relationship(
        "Organisation",
        foreign_keys=[organisation_id],
        back_populates="members",
    )
    roles = relationship(
        "Role",
        secondary=roles_users,
        backref=orm.backref("users", lazy="dynamic"),
    )
    wallet = relationship("IndividualWallet", uselist=False, back_populates="user")

    class AdminMeta:
        id = {"required": True, "read_only": True}
        # username = {"required": True, "read_only": True}
        email = {"required": True, "read_only": True}

        _columns = [
            "id",
            "email",
            "organisation_name",
        ]

        _form = [
            "id",
        ]

        _view = [
            "id",
        ]

        def getter(self, column, obj):
            if column == "organisation_name":
                return obj.organisation.name
            return getattr(obj, column)

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        if not self.fs_uniquifier:
            self.fs_uniquifier = uuid.uuid4().hex

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def name(self) -> str:
        return self.full_name

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    @property
    def communities(self) -> set[str]:
        if self.community_secondary:
            return {self.community_primary, self.community_secondary}
        else:
            return {self.community_primary}

    # Override Flask-Security
    def has_role(self, role: str | RoleEnum | Role) -> bool:
        """Returns `True` if the user identifies with the specified role.

        :param role: A role name or `Role` instance"""
        match role:
            case Role():
                return role in self.roles
            case RoleEnum():
                return role.name in (role.name for role in self.roles)
            case str():
                return role in (role.name for role in self.roles)
            case _:
                raise ValueError(f"Invalid role: {role}")


class Role(Base, RoleMixin):
    __tablename__ = "aut_role"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(80), unique=True)
    description: Mapped[str] = mapped_column(sa.String(255), default="")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"


# class User2(Base):
#     #
#     password_hash = sa.Column(sa.String(64), nullable=False)
#     password_salt = sa.Column(sa.String(64), nullable=False)
#
#     def set_password(self, password):
#         salt, key = generate_password_hash(password)
#         self.password_salt = salt
#         self.password_hash = key
#
#     def check_password(self, password):
#         return check_password_hash(password, self.password_salt, self.password_hash)
#
#     def gravatar(self, size):
#         digest = md5(self.email.lower().encode("utf-8")).hexdigest()
#         return "https://www.gravatar.com/avatar/{}?d=identicon&s={}".format(
#             digest, size
#         )

# class Group(Base):
#     __tablename__ = "group"


# class User(Base, UserMixin):
#     __tablename__ = "aut_user"
#     id = Column(Integer, primary_key=True)
#     email = Column(String(255), unique=True)
#     username = Column(String(255), unique=True, nullable=True)
#     password = Column(String(255), nullable=False)
#     last_login_at = Column(DateTime())
#     current_login_at = Column(DateTime())
#     last_login_ip = Column(String(100))
#     current_login_ip = Column(String(100))
#     login_count = Column(Integer)
#     active = Column(Boolean())
#     fs_uniquifier = Column(String(255), unique=True, nullable=False)
#     confirmed_at = Column(DateTime())
#     roles = relationship(
#         Role, secondary="aut_roles_users", backref=backref("users", lazy="dynamic")
#     )
