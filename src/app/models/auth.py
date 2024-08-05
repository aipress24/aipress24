# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import typing
import uuid

import sqlalchemy as sa
from aenum import StrEnum
from flask_security import RoleMixin, UserMixin
from sqlalchemy import JSON, DateTime, ForeignKey, String, orm
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

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
    email: Mapped[str] = mapped_column(unique=True, nullable=True)
    email_valid: Mapped[bool] = mapped_column(default=False)
    email_date_valid: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )
    email_secours: Mapped[str] = mapped_column(sa.String, nullable=True)
    email_secours_valid: Mapped[bool] = mapped_column(default=False)
    email_secours_date_valid: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )

    password: Mapped[str | None] = mapped_column()
    # remove _password_hash when going to bcrypt
    # _password_hash: Mapped[str | None] = mapped_column(sa.String(64))

    date_submit: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )
    user_valid: Mapped[bool] = mapped_column(default=False)
    user_date_valid: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )
    user_valid_comment: Mapped[str] = mapped_column(sa.String, default="")
    user_date_update: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, nullable=True, onupdate=func.now()
    )

    # from flask-security
    last_login_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime, nullable=True)
    current_login_at: Mapped[sa.DateTime] = mapped_column(sa.DateTime, nullable=True)
    last_login_ip: Mapped[str] = mapped_column(sa.DateTime, nullable=True)
    current_login_ip: Mapped[str] = mapped_column(sa.String, default="")
    login_count: Mapped[int] = mapped_column(sa.String, default=0)
    # Flask Security
    active: Mapped[bool] = mapped_column(default=False)
    fs_uniquifier: Mapped[str] = mapped_column(sa.String(64), unique=True)

    gcu_acceptation: Mapped[bool] = mapped_column(default=False)
    gcu_acceptation_date: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )

    community: Mapped[CommunityEnum] = mapped_column(
        sa.Enum(CommunityEnum), default=CommunityEnum.PRESS_MEDIA
    )

    gender: Mapped[str] = mapped_column(sa.String(1), default="?")
    presentation: Mapped[str] = mapped_column(sa.String, default="")
    first_name: Mapped[str] = mapped_column(sa.String(64), default="")
    last_name: Mapped[str] = mapped_column(sa.String(64), default="")

    photo: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=True)
    photo_filename: Mapped[str] = mapped_column(sa.String, default="")
    photo_carte_presse: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=True)
    photo_carte_presse_filename: Mapped[str] = mapped_column(sa.String, default="")
    pseudo: Mapped[str] = mapped_column(sa.String, default="")

    job_title: Mapped[str] = mapped_column(default="")
    job_description: Mapped[str] = mapped_column(default="")
    bio: Mapped[str] = mapped_column(default="")
    education: Mapped[str] = mapped_column(default="")
    # hobbies currently duplicated from PKYCProfile:
    hobbies: Mapped[str] = mapped_column(default="")

    tel_mobile: Mapped[str] = mapped_column(sa.String, default="")
    tel_mobile_valid: Mapped[bool] = mapped_column(default=False)
    tel_mobile_date_valid: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )

    organisation_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("crp_organisation.id", name="fk_aut_user_org_id")
    )

    # per order: nom_media, nom_media_insti, nom_agence_rp, nom_orga,
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
    profile: Mapped[KYCProfile] = relationship(back_populates="user")

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
        return {self.community}

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


class KYCProfile(Base):
    __tablename__ = "kyc_profile"

    id: Mapped[int] = mapped_column(primary_key=True, unique=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("aut_user.id"))
    user: Mapped[User] = relationship(back_populates="profile")
    profile_id: Mapped[str] = mapped_column(String, default="")
    profile_label: Mapped[str] = mapped_column(String, default="")
    profile_community: Mapped[str] = mapped_column(String, default="")
    info_professionnelle: Mapped[dict] = mapped_column(JSON, default="{}")
    match_making: Mapped[dict] = mapped_column(JSON, default="{}")
    hobbies: Mapped[dict] = mapped_column(JSON, default="{}")
    business_wall: Mapped[dict] = mapped_column(JSON, default="{}")
    date_update: Mapped[DateTime] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )


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
