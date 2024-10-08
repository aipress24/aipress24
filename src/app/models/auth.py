# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import typing
import uuid
from copy import deepcopy
from typing import Any

import sqlalchemy as sa
from aenum import StrEnum
from flask_security import RoleMixin, UserMixin
from sqlalchemy import JSON, DateTime, ForeignKey, orm
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.enums import CommunityEnum, ContactTypeEnum, OrganisationFamilyEnum
from app.modules.kyc.survey_model import get_survey_profile

from .base import Base
from .geoloc import GeoLocation

# from app.services.security import check_password_hash, generate_password_hash
from .mixins import Addressable

if typing.TYPE_CHECKING:
    from .organisation import Organisation

FIELD_TO_ORGA_FAMILY = {
    "nom_media": OrganisationFamilyEnum.MEDIA,
    "nom_media_instit": OrganisationFamilyEnum.INSTIT,
    "nom_agence_rp": OrganisationFamilyEnum.RP,
    "nom_orga": OrganisationFamilyEnum.AUTRE,
}


class RoleEnum(StrEnum):
    ADMIN = "admin"
    GUEST = "guest"

    PRESS_MEDIA = "journalist"
    PRESS_RELATIONS = "press_relations"
    EXPERT = "expert"
    ACADEMIC = "academic"
    TRANSFORMER = "transformer"


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
    email: Mapped[str] = mapped_column(sa.String, unique=True, nullable=True)
    # copy of email for clone:
    email_backup: Mapped[str] = mapped_column(sa.String, nullable=True, default="")
    email_secours: Mapped[str] = mapped_column(sa.String, nullable=True)

    password: Mapped[str | None] = mapped_column()

    is_clone: Mapped[bool] = mapped_column(default=False)
    # is_cloned: Mapped[bool] = mapped_column(default=False)  # usefull ?
    # security: not sure about id=0
    cloned_user_id: Mapped[int] = mapped_column(default=0)

    date_submit: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )
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
    last_login_ip: Mapped[str] = mapped_column(sa.String, default="", nullable=True)
    current_login_ip: Mapped[str] = mapped_column(sa.String, default="")
    login_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    # Flask Security
    active: Mapped[bool] = mapped_column(default=False)
    fs_uniquifier: Mapped[str] = mapped_column(sa.String(64), unique=True)
    deleted: Mapped[bool] = mapped_column(default=False)

    gcu_acceptation: Mapped[bool] = mapped_column(default=False)
    gcu_acceptation_date: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )

    community: Mapped[CommunityEnum] = mapped_column(
        sa.Enum(CommunityEnum), default=CommunityEnum.PRESS_MEDIA
    )

    gender: Mapped[str] = mapped_column(sa.String(1), default="?")
    first_name: Mapped[str] = mapped_column(sa.String(64), default="")
    last_name: Mapped[str] = mapped_column(sa.String(64), default="")

    photo: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=True)
    photo_filename: Mapped[str] = mapped_column(sa.String, default="")
    photo_carte_presse: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=True)
    photo_carte_presse_filename: Mapped[str] = mapped_column(sa.String, default="")

    # job_title: Mapped[str] = mapped_column(default="")
    # job_description: Mapped[str] = mapped_column(default="")

    tel_mobile: Mapped[str] = mapped_column(sa.String, default="")
    tel_mobile_valid: Mapped[bool] = mapped_column(default=False)
    tel_mobile_date_valid: Mapped[sa.DateTime] = mapped_column(
        sa.DateTime, server_default=func.now()
    )

    organisation_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("crp_organisation.id", name="fk_aut_user_org_id")
    )

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
    profile: Mapped[KYCProfile] = relationship(
        back_populates="user",
        cascade="save-update, merge, delete, delete-orphan",
    )

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

    @hybrid_property
    def job_title(self) -> str:
        return self.profile.profile_label

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

    def add_role(self, role: Role) -> bool:
        if self.has_role(role):
            return False
        self.roles.append(role)
        return True


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
    user_id: Mapped[int] = mapped_column(ForeignKey("aut_user.id", ondelete="CASCADE"))
    user: Mapped[User] = relationship(back_populates="profile")
    profile_id: Mapped[str] = mapped_column(sa.String, default="")
    profile_label: Mapped[str] = mapped_column(sa.String, default="")
    profile_community: Mapped[str] = mapped_column(sa.String, default="")
    contact_type: Mapped[str] = mapped_column(sa.String, default="")
    display_level: Mapped[int] = mapped_column(sa.Integer, default=1)
    # organisation_name: per order: nom_media, nom_media_insti, nom_agence_rp, nom_orga,
    organisation_name: Mapped[str] = mapped_column(sa.String, default="")
    presentation: Mapped[str] = mapped_column(sa.String, default="")
    show_contact_details: Mapped[dict] = mapped_column(JSON, default="{}")
    info_personnelle: Mapped[dict] = mapped_column(JSON, default="{}")
    info_professionnelle: Mapped[dict] = mapped_column(JSON, default="{}")
    match_making: Mapped[dict] = mapped_column(JSON, default="{}")
    business_wall: Mapped[dict] = mapped_column(JSON, default="{}")
    date_update: Mapped[DateTime] = mapped_column(
        DateTime, nullable=True, onupdate=func.now()
    )

    def get_value(self, field_name: str) -> Any:
        if field_name in KYCProfile.__dict__:
            return getattr(self, field_name)
        if field_name in self.show_contact_details:
            return self.show_contact_details[field_name]
        if field_name in self.info_professionnelle:
            return self.info_professionnelle[field_name]
        if field_name in self.info_personnelle:
            return self.info_personnelle[field_name]
        if field_name in self.match_making:
            return self.match_making[field_name]
        if field_name in self.business_wall:
            return self.business_wall[field_name]
        return ""

    def update_json_field(self, json_field: str, key: str, value: Any) -> None:
        tmp = deepcopy(getattr(self, json_field))
        tmp[key] = value
        setattr(self, json_field, tmp)

    def set_value(self, field_name: str, value: Any) -> None:
        if field_name in KYCProfile.__dict__:
            setattr(self, field_name, value)
            return
        elif field_name in self.show_contact_details:
            self.update_json_field("show_contact_details", field_name, value)
        elif field_name in self.info_professionnelle:
            self.update_json_field("info_professionnelle", field_name, value)
        elif field_name in self.info_personnelle:
            self.update_json_field("info_personnelle", field_name, value)
        elif field_name in self.match_making:
            self.update_json_field("match_making", field_name, value)
        elif field_name in self.business_wall:
            self.update_json_field("business_wall", field_name, value)

    @property
    def organisation_field_name_origin(self) -> str:
        survey_profile = get_survey_profile(self.profile_id)
        return survey_profile.organisation_field

    @property
    def organisation_family(self) -> OrganisationFamilyEnum:
        survey_profile = get_survey_profile(self.profile_id)
        family = FIELD_TO_ORGA_FAMILY.get(
            survey_profile.organisation_field, OrganisationFamilyEnum.AUTRE
        )
        return family  # type:ignore

    def deduce_organisation_name(self) -> None:
        field_name = self.organisation_field_name_origin
        if field_name:
            value = self.get_value(field_name)
            if isinstance(value, list):
                if value:
                    value = value[0]
                else:
                    value = ""
            self.organisation_name = value
        else:
            self.organisation_name = ""

    def induce_organisation_name(self, name: str) -> None:
        """Change Profile dependant organisation name field (and then the resulting
        organisation_name)
        """
        field_name = self.organisation_field_name_origin
        if field_name:
            current_value = self.get_value(field_name)
            if isinstance(current_value, list):
                if name:
                    new_value = [name]
                else:
                    new_value = []
            else:
                new_value = name
            self.set_value(field_name, new_value)
            self.organisation_name = name
        else:
            self.organisation_name = ""

    # unused
    # def contact_detail_visible_from(
    #     self,
    #     mobile_or_email: str,
    #     contact_type: str | ContactTypeEnum,
    # ) -> bool:
    #     if mobile_or_email not in {"mobile", "email"}:
    #         return False
    #     if isinstance(contact_type, ContactTypeEnum):
    #         key = f"{mobile_or_email}_{contact_type.name}"
    #     else:
    #         key = f"{mobile_or_email}_{contact_type}"
    #     return bool(self.show_contact_details.get(key))

    def all_contact_details(self) -> dict[str, Any]:
        """Return dict of contact deatails stored in DB for use
        in the multiple checkbox form of preferences.

        Data structure:

        {
        ...,
        "ETUDIANT":{
              "label": "Etudiants",
              "mobile_key": "mobile_ETUDIANT",
              "mobile": "checked",
              "email_key": "email_ETUDIANT",
              "email": "", # unchecked
            },
        ...
        }
        """

        def checked(flag: bool) -> str:
            if flag:
                return "checked"
            return ""

        data = {}
        contact_details = self.show_contact_details
        for contact_type in ContactTypeEnum:
            data[contact_type.name] = {}
            data[contact_type.name]["label"] = str(contact_type)
            for mode in ("mobile", "email"):
                key = f"{mode}_{contact_type.name}"
                data[contact_type.name][f"{mode}_key"] = key
                data[contact_type.name][mode] = checked(bool(contact_details.get(key)))
        return data

    def parse_form_contact_details(self, data: dict[str, str]) -> None:
        contact_details = deepcopy(self.show_contact_details)
        for contact_type in ContactTypeEnum:
            for mode in ("mobile", "email"):
                key = f"{mode}_{contact_type.name}"
                contact_details[key] = bool(data.get(key))
        self.show_contact_details = contact_details


def clone_user(orig_user: User) -> User:
    """Return a clone from the orig_user.

    The orig_user is unchanged by this function.
    # the orig_user.is_cloned to be set separately.
    """
    # do not clone a clone:
    if orig_user.is_clone:
        return orig_user
    # if orig_user.is_cloned:
    #     raise ValueError(
    #         f"User already cloned {orig_user.is_cloned} {orig_user}"
    #     )  # useful ?
    # security choosing to map all attri-butes one by one for now,
    # even if costly for mainatiance
    cloned_profile = clone_kycprofile(orig_user.profile)
    cloned_user = User(
        # id  # undefined at this point, autogenerated
        email=f"fake_{orig_user.id}@example.com",
        email_backup=orig_user.email,
        email_secours=orig_user.email_secours,  # no unicity on that field
        is_clone=True,
        # is_cloned=False,  # only original can be cloned
        cloned_user_id=orig_user.id,
        # date_submit automated by DB
        user_date_valid=orig_user.user_date_valid,
        user_valid_comment=orig_user.user_valid_comment,  # previous comment if any ?
        user_date_update=orig_user.user_date_update,
        # from flask-security
        last_login_at=orig_user.last_login_at,
        current_login_at=orig_user.current_login_at,
        last_login_ip=orig_user.last_login_ip,
        current_login_ip=orig_user.current_login_ip,
        login_count=orig_user.login_count,
        active=False,  # Do not activate clone
        fs_uniquifier=uuid.uuid4().hex,
        gcu_acceptation=orig_user.gcu_acceptation,
        gcu_acceptation_date=orig_user.gcu_acceptation_date,
        # actual user fields:
        community=orig_user.community,
        gender=orig_user.gender,
        first_name=orig_user.first_name,
        last_name=orig_user.last_name,
        photo=orig_user.photo,
        photo_filename=orig_user.photo_filename,
        photo_carte_presse=orig_user.photo_carte_presse,
        photo_carte_presse_filename=orig_user.photo_carte_presse_filename,
        # job_title=orig_user.job_title,
        tel_mobile=orig_user.tel_mobile,
        tel_mobile_valid=orig_user.tel_mobile_valid,
        tel_mobile_date_valid=orig_user.tel_mobile_date_valid,
        organisation_id=orig_user.organisation_id,
        geoloc_id=orig_user.geoloc_id,
        # geoloc  # check if needed
        profile_image_url=orig_user.profile_image_url,
        cover_image_url=orig_user.cover_image_url,
        status=orig_user.status,
        karma=orig_user.karma,
        organisation=orig_user.organisation,  # to verify: not to appear in members list ! maybe not for clone
        roles=orig_user.roles,  # maybe not for clone, only when merging ?
    )
    cloned_user.profile = cloned_profile
    return cloned_user


def merge_values_from_other_user(orig_user: User, modified_user: User) -> None:
    """Merge changes from (modified) cloned user.

    The function also reset the is_cloned flag of orig_user.
    """
    new_kyc_profile = clone_kycprofile(modified_user.profile)

    orig_user.email = modified_user.email_backup
    orig_user.email_backup = ""
    orig_user.email_secours = modified_user.email_secours
    orig_user.is_clone = False
    # orig_user.is_cloned = False  # clone will be dismissed
    orig_user.cloned_user_id = 0  # clone will be dismissed
    # date_submit automated by DB
    orig_user.user_date_valid = modified_user.user_date_valid
    orig_user.user_valid_comment = modified_user.user_valid_comment
    orig_user.user_date_update = modified_user.user_date_update
    # from flask-security
    orig_user.last_login_at = modified_user.last_login_at
    orig_user.current_login_at = modified_user.current_login_at
    orig_user.last_login_ip = modified_user.last_login_ip
    orig_user.current_login_ip = modified_user.current_login_ip
    orig_user.login_count = modified_user.login_count
    orig_user.active = (
        modified_user.active
    )  # user is considered as validated at this stage
    # unchanged orig_user.fs_uniquifier
    orig_user.gcu_acceptation = modified_user.gcu_acceptation
    orig_user.gcu_acceptation_date = modified_user.gcu_acceptation_date
    # actual user fields:
    orig_user.community = modified_user.community
    orig_user.gender = modified_user.gender
    orig_user.first_name = modified_user.first_name
    orig_user.last_name = modified_user.last_name
    orig_user.photo = modified_user.photo
    orig_user.photo_filename = modified_user.photo_filename
    orig_user.photo_carte_presse = modified_user.photo_carte_presse
    orig_user.photo_carte_presse_filename = modified_user.photo_carte_presse_filename
    # orig_user.job_title = modified_user.job_title
    orig_user.tel_mobile = modified_user.tel_mobile
    orig_user.tel_mobile_valid = modified_user.tel_mobile_valid
    orig_user.tel_mobile_date_valid = modified_user.tel_mobile_date_valid
    orig_user.organisation_id = modified_user.organisation_id
    orig_user.geoloc_id = modified_user.geoloc_id
    # geoloc  # check if needed
    orig_user.profile_image_url = modified_user.profile_image_url
    orig_user.cover_image_url = modified_user.cover_image_url
    orig_user.status = modified_user.status
    orig_user.karma = modified_user.karma
    orig_user.organisation = modified_user.organisation
    orig_user.roles = modified_user.roles  # maybe not for clone, only when merging

    # orig_user.profile = modified_user.profile
    orig_user.profile = new_kyc_profile


def clone_kycprofile(orig_profile: KYCProfile) -> KYCProfile:
    """Return a duplicate a KYCProfile.

    Does not duplicate id, user_id, user, date_update fields.
    Does not store information if object is an original or clone.
    """
    return KYCProfile(
        # id  # undefined at this point, autogenerated
        # user_id # undefined at this point, generated when put on user
        # user # undefined at this point, generated when put on user
        profile_id=orig_profile.profile_id,
        profile_label=orig_profile.profile_label,
        profile_community=orig_profile.profile_community,
        contact_type=orig_profile.contact_type,
        display_level=orig_profile.display_level,
        organisation_name=orig_profile.organisation_name,
        presentation=orig_profile.presentation,
        show_contact_details=orig_profile.show_contact_details,
        info_personnelle=orig_profile.info_personnelle,
        info_professionnelle=orig_profile.info_professionnelle,
        match_making=orig_profile.match_making,
        business_wall=orig_profile.business_wall,
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
