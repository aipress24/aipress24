"""Authentication models for users, roles, and KYC profiles."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import typing
import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, ClassVar

import arrow
import sqlalchemy as sa
from advanced_alchemy.types.file_object import FileObject, StoredObject
from flask_security import RoleMixin, UserMixin
from sqlalchemy import JSON, DateTime, ForeignKey, orm
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy_utils import ArrowType

from app.enums import ContactTypeEnum, OrganisationTypeEnum, RoleEnum
from app.modules.kyc.survey_model import get_survey_profile

from .base import Base

# from app.services.security import check_password_hash, generate_password_hash
from .mixins import Addressable, LifeCycleMixin

# from .geoloc import GeoLocation

if typing.TYPE_CHECKING:
    from .organisation import Organisation

FIELD_TO_ORGA_FAMILY = {
    "nom_media": OrganisationTypeEnum.MEDIA,
    "nom_media_instit": OrganisationTypeEnum.OTHER,
    "nom_agence_rp": OrganisationTypeEnum.COM,
    "nom_orga": OrganisationTypeEnum.OTHER,
}

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


class User(LifeCycleMixin, Addressable, UserMixin, Base):
    __tablename__ = "aut_user"

    id: Mapped[int] = mapped_column(primary_key=True)

    # username: Mapped[str] = mapped_column(index=True, unique=True)
    email: Mapped[str] = mapped_column(unique=True, nullable=True)
    # copy of email for clone:
    email_safe_copy: Mapped[str] = mapped_column(nullable=True, default="")
    email_secours: Mapped[str] = mapped_column(nullable=True)

    password: Mapped[str | None] = mapped_column()

    is_clone: Mapped[bool] = mapped_column(default=False)
    # is_cloned: Mapped[bool] = mapped_column(default=False)  # usefull ?
    # security: not sure about id=0
    cloned_user_id: Mapped[int] = mapped_column(default=0)

    submited_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow
    )
    validated_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True, default=None
    )
    validation_status: Mapped[str] = mapped_column(default="")
    # from LifeCycleMixin : created_at
    # from LifeCycleMixin : deleted_at
    modified_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True, onupdate=arrow.utcnow
    )

    # from flask-security
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_ip: Mapped[str] = mapped_column(default="", nullable=True)
    current_login_ip: Mapped[str] = mapped_column(default="")
    login_count: Mapped[int] = mapped_column(sa.Integer, default=0)
    # Flask Security
    active: Mapped[bool] = mapped_column(default=False)
    fs_uniquifier: Mapped[str] = mapped_column(sa.String(64), unique=True)

    gcu_acceptation: Mapped[bool] = mapped_column(default=False)
    gcu_acceptation_date: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), server_default=func.now()
    )

    gender: Mapped[str] = mapped_column(sa.String(1), default="?")
    first_name: Mapped[str] = mapped_column(sa.String(64), default="")
    last_name: Mapped[str] = mapped_column(sa.String(64), default="")

    photo_image: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )
    photo_carte_presse_image: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )
    # job_title: Mapped[str] = mapped_column(default="")
    # job_description: Mapped[str] = mapped_column(default="")

    tel_mobile: Mapped[str] = mapped_column(default="")
    tel_mobile_validated_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True, default=None
    )

    organisation_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("crp_organisation.id", name="fk_aut_user_org_id")
    )

    # TODO
    # geoloc_id = sa.Column(sa.Integer, sa.ForeignKey("geo_loc.id"), nullable=True)
    # geoloc_id: Mapped[int | None] = mapped_column(
    #     sa.BigInteger, sa.ForeignKey("geo_loc.id")
    # )
    # geoloc = relationship(GeoLocation)

    # TODO: use content repository
    cover_image: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )

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
        id: ClassVar[dict] = {"required": True, "read_only": True}
        # username = {"required": True, "read_only": True}
        email: ClassVar[dict] = {"required": True, "read_only": True}

        _columns: ClassVar[list] = [
            "id",
            "email",
            "organisation_name",
        ]

        _form: ClassVar[list] = [
            "id",
        ]

        _view: ClassVar[list] = [
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

    @hybrid_property
    def job_title(self) -> str:
        return self.profile.profile_label

    @hybrid_property
    def metiers(self) -> list[str]:
        return self.profile.metiers

    @hybrid_property
    def tous_metiers(self) -> set[str]:
        return set(self.profile.metiers + self.profile.metiers_autres)

    @hybrid_property
    def metier_fonction(self) -> str:
        return self.profile.metier_fonction

    @hybrid_property
    def organisation_name(self) -> str:
        if self.organisation:
            return self.organisation.name
        return ""

    def first_community(self) -> RoleEnum:
        community: RoleEnum
        for community in (  # type: ignore[invalid-assignment]
            RoleEnum.PRESS_MEDIA,
            RoleEnum.PRESS_RELATIONS,
            RoleEnum.EXPERT,
            RoleEnum.TRANSFORMER,
            RoleEnum.ACADEMIC,
        ):
            if community.name in (role.name for role in self.roles):
                return community
        msg = f"Unknown community for {self}: {self.roles=}"
        raise RuntimeError(msg)

    # Override Flask-Security
    def has_role(self, role: str | RoleEnum | Role) -> bool:  # type: ignore[override]
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
                msg = f"Invalid role: {role}"
                raise ValueError(msg)

    def add_role(self, role: Role) -> bool:
        if self.has_role(role):
            return False
        self.roles.append(role)
        return True

    def remove_role(self, role: str | RoleEnum | Role) -> None:
        """Remove the role of the user role list."""
        match role:
            case Role():
                self.roles.remove(role)
            case RoleEnum():
                for current in self.roles:
                    if role.name == current.name:
                        self.roles.remove(current)
                        break
            case str():
                for current in self.roles:
                    if role == current.name:
                        self.roles.remove(current)
                        break
            case _:
                msg = f"Invalid role: {role}"
                raise ValueError(msg)

    @property
    def is_manager(self) -> bool:
        return self.has_role(RoleEnum.MANAGER)

    @property
    def is_leader(self) -> bool:
        return self.has_role(RoleEnum.LEADER)

    def is_member(self, org_id: int) -> bool:
        if not self.organisation_id:
            return False
        return self.organisation_id == org_id

    def cover_image_signed_url(self, expires_in: int = 3600) -> str:
        file_obj: FileObject | None = self.cover_image
        if file_obj is None:
            return "/static/img/transparent-square.png"
        try:
            return file_obj.sign(expires_in=expires_in, for_upload=False)
        except RuntimeError as e:
            msg = f"Storage failed to sign URL for banner user.id : {self.id}, key {file_obj.path}: {e}"
            raise RuntimeError(msg) from e

    def photo_image_signed_url(self, expires_in: int = 3600) -> str:
        file_obj: FileObject | None = self.photo_image
        if file_obj is None:
            return "/static/img/transparent-square.png"
        try:
            return file_obj.sign(expires_in=expires_in, for_upload=False)
        except RuntimeError as e:
            msg = f"Storage failed to sign URL for photo user.id : {self.id}, key {file_obj.path}: {e}"
            raise RuntimeError(msg) from e

    def photo_carte_presse_image_signed_url(self, expires_in: int = 3600) -> str:
        file_obj: FileObject | None = self.photo_image
        if file_obj is None:
            return "/static/img/transparent-square.png"
        try:
            return file_obj.sign(expires_in=expires_in, for_upload=False)
        except RuntimeError as e:
            msg = f"Storage failed to sign URL for carte presse user.id : {self.id}, key {file_obj.path}: {e}"
            raise RuntimeError(msg) from e


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

    profile_id: Mapped[str] = mapped_column(default="")
    profile_code: Mapped[str] = mapped_column(default="")
    profile_label: Mapped[str] = mapped_column(default="")
    profile_community: Mapped[str] = mapped_column(default="")

    contact_type: Mapped[str] = mapped_column(default="")
    display_level: Mapped[int] = mapped_column(sa.Integer, default=1)
    presentation: Mapped[str] = mapped_column(default="")
    show_contact_details: Mapped[dict] = mapped_column(JSON, default=dict)
    info_personnelle: Mapped[dict] = mapped_column(JSON, default=dict)
    info_professionnelle: Mapped[dict] = mapped_column(JSON, default=dict)
    match_making: Mapped[dict] = mapped_column(JSON, default=dict)
    info_hobby: Mapped[dict] = mapped_column(JSON, default=dict)
    business_wall: Mapped[dict] = mapped_column(JSON, default=dict)
    date_update: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    def has_field_name(self, field_name: str) -> bool:
        """Check if 'field_name' is a known key of the KYCProfile."""
        return any(
            field_name in d
            for d in (
                KYCProfile.__dict__,
                self.show_contact_details,
                self.info_professionnelle,
                self.info_personnelle,
                self.match_making,
                self.info_hobby,
                self.business_wall,
            )
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
        if field_name in self.info_hobby:
            return self.info_hobby[field_name]
        if field_name in self.business_wall:
            return self.business_wall[field_name]
        return ""

    @property
    def country(self) -> str:
        return self.info_professionnelle["pays_zip_ville"] or ""

    @hybrid_property
    def code_postal(self) -> str:
        """Return the zip code"""
        pays_zip_ville = self.info_professionnelle["pays_zip_ville_detail"]
        if not pays_zip_ville:
            return ""
        if isinstance(pays_zip_ville, list):
            pays_zip_ville = pays_zip_ville[0]
        try:
            return pays_zip_ville.split()[2]
        except IndexError:
            return ""

    @code_postal.expression
    def code_postal(cls):
        """SQL expression for the zip code property."""
        extracted = cls.info_professionnelle["pays_zip_ville_detail"].op("->>")(0)
        return func.coalesce(func.split_part(extracted, " ", 3))

    @hybrid_property
    def departement(self) -> str:
        """Return the 2 first digit of zip code"""
        pays_zip_ville = self.info_professionnelle["pays_zip_ville_detail"]
        if not pays_zip_ville:
            return ""
        if isinstance(pays_zip_ville, list):
            pays_zip_ville = pays_zip_ville[0]
        try:
            return pays_zip_ville.split()[2][:2]
        except IndexError:
            return ""

    @departement.expression
    def departement(cls):
        """SQL expression for the departement property."""
        extracted = cls.info_professionnelle["pays_zip_ville_detail"].op("->>")(0)
        expression = func.coalesce(
            func.substring(func.split_part(extracted, " ", 3), 1, 2),
            "",
        )
        return expression

    @hybrid_property
    def ville(self) -> str:
        """Return the 4th part of pays_zip_ville_detail"""
        pays_zip_ville = self.info_professionnelle.get("pays_zip_ville_detail")
        if not pays_zip_ville:
            return ""
        if isinstance(pays_zip_ville, list):
            pays_zip_ville = pays_zip_ville[0]
        try:
            return pays_zip_ville.split()[3]
        except IndexError:
            return ""

    @ville.expression
    def ville(cls):
        """SQL expression for the ville property."""
        extracted = cls.info_professionnelle["pays_zip_ville_detail"].op("->>")(0)
        expression = func.coalesce(
            func.split_part(extracted, " ", 4),
            "",
        )
        return expression

    @property
    def metier_fonction(self) -> str:
        if fonctions := self.fonctions_journalisme:
            return fonctions[0]
        if metiers := self.metiers:
            return metiers[0]
        return ""

    @property
    def metiers(self) -> list[str]:
        return self.info_personnelle["metier_principal_detail"] or []

    @property
    def metiers_autres(self) -> list[str]:
        return self.info_personnelle["metier_detail"] or []

    @property
    def secteurs_activite(self) -> list[str]:
        return (
            self.info_professionnelle.get("secteurs_activite_medias_detail", [])
            + self.info_professionnelle.get("secteurs_activite_rp_detail", [])
            + self.info_professionnelle.get("secteurs_activite_detailles_detail", [])
        )

    @property
    def toutes_fonctions(self) -> list[str]:
        return (
            self.match_making.get("fonctions_journalisme", [])
            + self.match_making.get("fonctions_pol_adm_detail", [])
            + self.match_making.get("fonctions_org_priv_detail", [])
            + self.match_making.get("fonctions_ass_syn_detail", [])
        )

    @property
    def fonctions_journalisme(self) -> list[str]:
        return self.match_making.get("fonctions_journalisme", [])

    @property
    def fonctions_pol_adm_detail(self) -> list[str]:
        return self.match_making.get("fonctions_pol_adm_detail", [])

    @property
    def fonctions_org_priv_detail(self) -> list[str]:
        return self.match_making.get("fonctions_org_priv_detail", [])

    @property
    def fonctions_ass_syn_detail(self) -> list[str]:
        return self.match_making.get("fonctions_ass_syn_detail", [])

    @property
    def type_entreprise_media(self) -> list[str]:
        return self.info_professionnelle.get("type_entreprise_media", [])

    @property
    def type_presse_et_media(self) -> list[str]:
        return self.info_professionnelle.get("type_presse_et_media", [])

    @property
    def langues(self) -> list[str]:
        return self.info_personnelle.get("langues", [])

    @property
    def competences(self) -> list[str]:
        return self.info_personnelle.get("competences", [])

    @property
    def competences_journalisme(self) -> list[str]:
        return self.info_personnelle.get("competences_journalisme", [])

    @property
    def type_organisation(self) -> list[str]:
        return self.info_professionnelle.get("type_orga_detail", [])

    @property
    def taille_organisation(self) -> list[str]:
        return self.info_professionnelle.get("taille_orga", [])

    def get_first_value(self, field_name: str) -> str:
        value = self.get_value(field_name)
        if isinstance(value, list):
            if value:
                return value[0]
            return ""
        return value

    def get_all_bw_trigger(self) -> list[str]:
        """Return names of all business_wall trigger with True value."""
        return [key for key, val in self.business_wall.items() if val]

    def get_first_bw_trigger(self) -> str:
        """Return name of the business_wall trigger with True value,
        or an empty string
        """
        triggers = self.get_all_bw_trigger()
        if triggers:
            return triggers[0]
        return ""

    def update_json_field(self, json_field: str, key: str, value: Any) -> None:
        tmp = deepcopy(getattr(self, json_field))
        tmp[key] = value
        setattr(self, json_field, tmp)

    def set_value(self, field_name: str, value: Any) -> None:
        if field_name in KYCProfile.__dict__:
            setattr(self, field_name, value)
            return
        if field_name in self.show_contact_details:
            self.update_json_field("show_contact_details", field_name, value)
        elif field_name in self.info_professionnelle:
            self.update_json_field("info_professionnelle", field_name, value)
        elif field_name in self.info_personnelle:
            self.update_json_field("info_personnelle", field_name, value)
        elif field_name in self.match_making:
            self.update_json_field("match_making", field_name, value)
        elif field_name in self.info_hobby:
            self.update_json_field("info_hobby", field_name, value)
        elif field_name in self.business_wall:
            self.update_json_field("business_wall", field_name, value)

    @property
    def organisation_field_name_origin(self) -> str:
        survey_profile = get_survey_profile(self.profile_id)
        return survey_profile.organisation_field

    @property
    def organisation_family(self) -> OrganisationTypeEnum:
        survey_profile = get_survey_profile(self.profile_id)
        family = FIELD_TO_ORGA_FAMILY.get(
            survey_profile.organisation_field, OrganisationTypeEnum.OTHER
        )
        return family  # type:ignore

    def deduce_organisation_name(self) -> None:
        return
        # field_name = self.organisation_field_name_origin
        # if field_name:
        #     value = self.get_value(field_name)
        #     if isinstance(value, list):
        #         if value:
        #             value = value[0]
        #         else:
        #             value = ""
        #     self.organisation_name = value
        # else:
        #     self.organisation_name = ""

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

        data: dict[str, dict[str, str]] = {}
        contact_details = self.show_contact_details
        for contact_type in ContactTypeEnum:  # type: ignore[not-iterable]
            data[contact_type.name] = {}
            data[contact_type.name]["label"] = str(contact_type)
            for mode in ("mobile", "email", "email_relation_presse"):
                key = f"{mode}_{contact_type.name}"
                data[contact_type.name][f"{mode}_key"] = key
                data[contact_type.name][mode] = checked(bool(contact_details.get(key)))
        return data

    def parse_form_contact_details(self, data: dict[str, str]) -> None:
        contact_details = deepcopy(self.show_contact_details)
        for contact_type in ContactTypeEnum:  # type: ignore[not-iterable]
            for mode in ("mobile", "email", "email_relation_presse"):
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
        email=f"fake_{uuid.uuid4().hex}@example.com",
        email_safe_copy=orig_user.email,
        email_secours=orig_user.email_secours,  # no unicity on that field
        is_clone=True,
        # is_cloned=False,  # only original can be cloned
        cloned_user_id=orig_user.id,
        # submited_at automated by DB
        validated_at=orig_user.validated_at,
        validation_status=orig_user.validation_status,  # previous comment if any ?
        created_at=orig_user.created_at,
        modified_at=orig_user.modified_at,
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
        gender=orig_user.gender,
        first_name=orig_user.first_name,
        last_name=orig_user.last_name,
        photo_image=orig_user.photo_image,
        photo_carte_presse_image=orig_user.photo_carte_presse_image,
        # job_title=orig_user.job_title,
        tel_mobile=orig_user.tel_mobile,
        tel_mobile_validated_at=orig_user.tel_mobile_validated_at,
        organisation_id=orig_user.organisation_id,
        cover_image=orig_user.cover_image,
        status=orig_user.status,
        karma=orig_user.karma,
        organisation=orig_user.organisation,  # to verify: not to appear in members list ! maybe not for clone
        roles=orig_user.roles,  # maybe not for clone, only when merging ?
    )
    for key in orig_user.addr_attributes:
        setattr(cloned_user, key, getattr(orig_user, key))
    cloned_user.profile = cloned_profile
    return cloned_user


def merge_values_from_other_user(orig_user: User, modified_user: User) -> None:
    """Merge changes from (modified) cloned user.

    The function also reset the is_cloned flag of orig_user.
    """
    new_kyc_profile = clone_kycprofile(modified_user.profile)

    orig_user.email = modified_user.email_safe_copy
    orig_user.email_safe_copy = ""
    orig_user.email_secours = modified_user.email_secours
    orig_user.is_clone = False
    # orig_user.is_cloned = False  # clone will be dismissed
    orig_user.cloned_user_id = 0  # clone will be dismissed
    # submited_at automated by DB
    orig_user.validated_at = modified_user.validated_at
    orig_user.validation_status = modified_user.validation_status
    orig_user.created_at = modified_user.created_at
    orig_user.modified_at = modified_user.modified_at
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
    orig_user.gender = modified_user.gender
    orig_user.first_name = modified_user.first_name
    orig_user.last_name = modified_user.last_name
    orig_user.photo_image = modified_user.photo_image
    orig_user.photo_carte_presse_image = modified_user.photo_carte_presse_image
    # orig_user.job_title = modified_user.job_title
    orig_user.tel_mobile = modified_user.tel_mobile
    orig_user.tel_mobile_validated_at = modified_user.tel_mobile_validated_at
    orig_user.organisation_id = modified_user.organisation_id
    # orig_user.geoloc_id = modified_user.geoloc_id
    # geoloc  # check if needed
    orig_user.cover_image = modified_user.cover_image
    orig_user.status = modified_user.status
    orig_user.karma = modified_user.karma
    orig_user.organisation = modified_user.organisation
    orig_user.roles = modified_user.roles  # maybe not for clone, only when merging

    for key in modified_user.addr_attributes:
        setattr(orig_user, key, getattr(modified_user, key))

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
        profile_code=orig_profile.profile_code,
        profile_label=orig_profile.profile_label,
        profile_community=orig_profile.profile_community,
        contact_type=orig_profile.contact_type,
        display_level=orig_profile.display_level,
        presentation=orig_profile.presentation,
        show_contact_details=orig_profile.show_contact_details,
        info_personnelle=orig_profile.info_personnelle,
        info_professionnelle=orig_profile.info_professionnelle,
        match_making=orig_profile.match_making,
        info_hobby=orig_profile.info_hobby,
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
