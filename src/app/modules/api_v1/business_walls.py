# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The Business Walls the caller manages, as the « Contenus » form edits them.

Subscribing goes through Stripe, on the site. Only an administrator may open a
Business Wall here, and for their own organisation.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any
from uuid import UUID

import arrow
from loguru import logger

from app.enums import BWStatus, RoleEnum
from app.flask.extensions import db
from app.lib.file_object_utils import InvalidImageError, store_image
from app.modules.bw.bw_activation.bw_creation import (
    create_new_free_bw_record,
    create_new_paid_bw_record,
)
from app.modules.bw.bw_activation.config import BW_TYPES, DEPRECATED_BW_TYPES
from app.modules.bw.bw_activation.models.business_wall import BusinessWall
from app.modules.bw.bw_activation.user_utils import (
    can_activate_business_wall,
    get_active_business_wall_for_organisation,
    get_manageable_business_walls_for_user,
)
from app.modules.bw.bw_activation.utils import is_bw_manager
from app.settings.constants import MAX_IMAGE_SIZE

from .answers import (
    CITIES,
    COUNTRIES,
    DETAIL,
    GROUPS,
    AnswerField,
    Kind,
    check_answers,
    check_web_url,
    missing_answers,
    read_answers,
)
from .writes import WriteError

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage

    from app.models.auth import User

# Of a picture → the column of the image, and of its copyright.
PICTURES = {
    "logo": ("logo_image", "logo_image_copyright"),
    "cover": ("cover_image", "cover_image_copyright"),
}
_MAX_TEXT = 500
_MAX_LINE = 200

_ALL = frozenset(BW_TYPES)
_PRESS = frozenset({"media", "news_agency"})
_LEADERS = frozenset({"leaders_experts", "transformers"})


def _text(
    name: str, label: str, types: frozenset[str] = _ALL, **options: Any
) -> tuple[frozenset[str], AnswerField]:
    options = {"max_length": _MAX_LINE, **options}
    return types, AnswerField(name, label, Kind.TEXT, **options)


def _choices(
    name: str,
    label: str,
    vocabulary: str,
    types: frozenset[str] = _ALL,
    **options: Any,
) -> tuple[frozenset[str], AnswerField]:
    field = AnswerField(name, label, Kind.CHOICES, vocabulary=vocabulary, **options)
    return types, field


def _choice(
    name: str,
    label: str,
    vocabulary: str,
    types: frozenset[str] = _ALL,
    **options: Any,
) -> tuple[frozenset[str], AnswerField]:
    field = AnswerField(name, label, Kind.CHOICE, vocabulary=vocabulary, **options)
    return types, field


def _nested(
    name: str,
    label: str,
    vocabulary: str,
    types: frozenset[str] = _ALL,
    **options: Any,
) -> tuple[tuple[frozenset[str], AnswerField], ...]:
    return (
        _choices(name, label, f"{vocabulary}{GROUPS}", types, **options),
        _choices(
            f"{name}{DETAIL}", f"{label} (détail)", vocabulary, types, parent=name
        ),
    )


# The fields of the form, and the types of Business Wall which have them.
_FIELDS: tuple[tuple[frozenset[str], AnswerField], ...] = (
    _text("name", "Nom de votre Business Wall", required=True),
    *_nested(
        "type_organisation",
        "Type d'organisation",
        "type_organisation_detail",
        _ALL - {"micro", "pr"},
        max_items=1,
    ),
    _text(
        "name_group",
        "Groupe ou entité de rattachement",
        _LEADERS | {"corporate_media", "pr", "academics"},
    ),
    _text("siren", "Numéro de SIREN", required=True),
    _text("tva", "Numéro de TVA intracommunautaire"),
    _text("agrement", "Agrément", _PRESS, max_length=_MAX_TEXT),
    _text("name_official", "Nom officiel", _PRESS | _LEADERS),
    _text("name_institution", "Nom de l'institution", frozenset({"academics"})),
    _choices(
        "type_entreprise_media",
        "Type d'entreprise de presse et média",
        "type_entreprises_medias",
        _PRESS | {"micro", "corporate_media"},
    ),
    _choices(
        "type_agence_rp", "Type de PR Agency", "type_agence_rp", frozenset({"pr"})
    ),
    _text("clients", "Principaux clients", frozenset({"pr"}), max_length=_MAX_TEXT),
    _text("presentation", "Présentation", max_length=_MAX_TEXT),
    _choices(
        "type_presse_et_media",
        "Type de presse et média",
        "media_type",
        _PRESS | {"micro", "corporate_media"},
    ),
    _text(
        "positionnement_editorial",
        "Positionnement éditorial",
        _PRESS | {"micro", "corporate_media"},
        max_length=_MAX_TEXT,
    ),
    _text(
        "audience_cible",
        "Audience cible",
        _PRESS | {"micro", "corporate_media"},
        max_length=_MAX_TEXT,
    ),
    _choice("periodicite", "Périodicité", "periodicite", _PRESS | {"corporate_media"}),
    *_nested("secteurs_activite", "Secteurs d'activité", "secteur_detaille"),
    _choice("taille_orga", "Taille de l'organisation", "taille_organisation"),
    *_nested(
        "interest_political",
        "Centres d'intérêt : tissu politique et administratif",
        "interet_politique",
    ),
    *_nested(
        "interest_economics",
        "Centres d'intérêt : tissu économique et culturel privé",
        "interet_orga",
    ),
    *_nested(
        "interest_association", "Centres d'intérêt : tissu associatif", "interet_asso"
    ),
    _text("tel_standard", "Téléphone du standard"),
    _text("postal_address", "Adresse du siège social", max_length=_MAX_TEXT),
    _choice("pays_zip_ville", "Pays", COUNTRIES),
    _choice(
        f"pays_zip_ville{DETAIL}",
        "Code postal et ville",
        CITIES,
        parent="pays_zip_ville",
    ),
    _text("geolocalisation", "Géolocalisation"),
    _text("site_url", "URL du site web", check=check_web_url),
    _text("logo_image_copyright", "Copyright de l'image du logo"),
    _text("cover_image_copyright", "Copyright de l'image du bandeau"),
)


def business_wall_types() -> list[dict[str, Any]]:
    return [
        {"id": bw_type, "label": info["name"], "free": bool(info["free"])}
        for bw_type, info in BW_TYPES.items()
        if bw_type not in DEPRECATED_BW_TYPES
    ]


def business_wall_fields(bw_type: str) -> list[AnswerField]:
    return [field for types, field in _FIELDS if bw_type in types]


def my_business_walls(user: User) -> list[BusinessWall]:
    """Those the caller manages; publishing for an organisation is not enough."""
    return [
        wall
        for wall in get_manageable_business_walls_for_user(user)
        if wall.status == BWStatus.ACTIVE.value and is_bw_manager(user, wall)
    ]


def my_business_wall(user: User, identifier: UUID) -> BusinessWall | None:
    return next((w for w in my_business_walls(user) if w.id == identifier), None)


def business_wall_view(wall: BusinessWall) -> dict[str, Any]:
    fields = business_wall_fields(wall.bw_type)
    answers = _answers(wall, fields)
    return {
        "id": wall.id,
        "name": wall.name_safe,
        "bw_type": wall.bw_type,
        "type_label": BW_TYPES[wall.bw_type]["name"],
        "organisation_id": wall.organisation_id,
        "logo": wall.logo_image,
        "cover": wall.cover_image,
        "answers": answers,
        "missing": missing_answers(fields, answers),
        "fields": fields,
    }


def create_business_wall(user: User, bw_type: str) -> BusinessWall:
    """Open a Business Wall for the caller's organisation, without payment."""
    if not user.has_role(RoleEnum.ADMIN):
        raise WriteError(
            403, "Only an administrator may do this: subscribe on the site."
        )
    if bw_type not in {each["id"] for each in business_wall_types()}:
        raise WriteError(422, f"bw_type: {bw_type!r} is not a type of Business Wall.")
    organisation = user.organisation
    if organisation is None or organisation.deleted_at is not None:
        raise WriteError(
            409, "You have no organisation: name one in your profile first."
        )
    if not can_activate_business_wall(user):
        raise WriteError(403, "Your type of profile may not open a Business Wall.")
    if get_active_business_wall_for_organisation(organisation) is not None:
        raise WriteError(409, f"{organisation.name} already has a Business Wall.")

    is_free = BW_TYPES[bw_type]["free"]
    create = create_new_free_bw_record if is_free else create_new_paid_bw_record
    # What the steps of the subscription leave in the session of a member.
    if not create({"bw_activated": True, "bw_type": bw_type, "payer_is_owner": True}):
        db.session.rollback()
        raise WriteError(409, "The site could not open the Business Wall.")
    user.cgv_accepted_at = arrow.utcnow()
    db.session.commit()
    wall = get_active_business_wall_for_organisation(organisation)
    assert wall is not None
    logger.info(
        "Business Wall {} ({}) opened without payment by administrator {} for {}",
        wall.id,
        bw_type,
        user.id,
        organisation.id,
    )
    return wall


def update_business_wall(
    wall: BusinessWall, given: Mapping[str, Any], *, dry_run: bool
) -> dict[str, Any]:
    """Apply a partial update, and say what it changes."""
    fields = business_wall_fields(wall.bw_type)
    changes, errors = check_answers(fields, _answers(wall, fields), given)
    if errors:
        raise WriteError(422, "Some answers are not accepted.", errors)
    if changes and not dry_run:
        for name, value in changes.items():
            setattr(wall, name, value)
        organisation = wall.get_organisation()
        if "name" in changes and organisation:
            organisation.bw_name = wall.name
        if f"pays_zip_ville{DETAIL}" in changes:
            wall.update_location_fields()
        db.session.commit()
    return {"changed": [*changes], "dry_run": dry_run}


def set_picture(
    wall: BusinessWall, picture: str, upload: FileStorage, copyright: str | None
) -> None:
    """Replace the logo or the cover, and its copyright when one is given."""
    # Reading up to the limit, which is itself refused, is enough to tell.
    content = upload.stream.read(MAX_IMAGE_SIZE)
    if len(content) >= MAX_IMAGE_SIZE:
        raise WriteError(413, "The image is too large.")
    column, copyright_column = PICTURES[picture]
    try:
        setattr(wall, column, store_image(content, upload.filename or ""))
    except InvalidImageError as exc:
        raise WriteError(422, str(exc)) from exc
    if copyright is not None:
        setattr(wall, copyright_column, copyright.strip())
    db.session.commit()


def _answers(wall: BusinessWall, fields: list[AnswerField]) -> dict[str, Any]:
    return read_answers(fields, {f.name: getattr(wall, f.name) for f in fields})
