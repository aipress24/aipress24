# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The professional profile of the caller, as the form of the site edits it.

The identity used to log in, the pictures and the terms of use are left to the form.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from email_validator import EmailNotValidError, validate_email
from markupsafe import Markup

from app.flask.extensions import db
from app.models.auth import User
from app.modules.kyc.dynform import (
    MAX_STRING,
    MAX_TEL,
    MAX_TEXTAREA,
    MAX_TEXTAREA300,
)
from app.modules.kyc.ontology_loader import ONTOLOGY_MAP
from app.modules.kyc.survey_dataclass import SurveyField, SurveyProfile
from app.modules.kyc.survey_model import (
    get_survey_model,
    get_survey_profile,
    get_survey_profile_ids,
)
from app.modules.kyc.views import (
    is_kept_by_business_wall,
    member_answers,
    update_member,
)

from .answers import (
    CITIES,
    COUNTRIES,
    DETAIL,
    GROUPS,
    AnswerField,
    Answers,
    Kind,
    check_answers,
    check_web_url,
    missing_answers,
    read_answers,
)
from .writes import WriteError

if TYPE_CHECKING:
    from app.models.auth import KYCProfile

NOT_EDITABLE = frozenset({"email", "password", "photo", "photo_square", "boolink"})
_MAX_NAME = 200
# Two questions, whose labels are separated by a semicolon.
_DOUBLE = frozenset({"multidual", "country"})


def check_email(value: str) -> str:
    try:
        validate_email(value, check_deliverability=False)
    except EmailNotValidError:
        return "is not an email address"
    return ""


_TEXTS: dict[str, dict[str, Any]] = {
    "string": {"max_length": MAX_STRING},
    "textarea": {"max_length": MAX_TEXTAREA},
    "textarea300": {"max_length": MAX_TEXTAREA300},
    "tel": {"max_length": MAX_TEL},
    "email_free": {"max_length": MAX_STRING, "check": check_email},
    "url": {"max_length": MAX_STRING, "check": check_web_url},
}


def profile_types() -> list[dict[str, str]]:
    """Every type of profile, as the first page of the form lists them."""
    return [
        {
            "id": profile.id,
            "label": profile.label,
            "community": profile.community.name,
        }
        for profile in get_survey_model()["profiles"]
    ]


def profile_view(user: User, type_id: str | None = None) -> dict[str, Any]:
    """The profile, with the questions of its type or of another one."""
    profile = _require_profile(user)
    survey = _survey(type_id or profile.profile_id)
    fields = profile_fields(survey)
    answers = read_answers(fields, member_answers(user))
    return {
        "type": survey.id,
        "type_label": survey.label,
        "community": survey.community.name,
        "awaiting_validation": _awaits_validation(user),
        "organisation_name": user.organisation_name,
        "answers": answers,
        "missing": missing_answers(fields, answers),
        "fields": fields,
    }


def update_profile(
    user: User, data: Mapping[str, Any], *, dry_run: bool
) -> dict[str, Any]:
    """Apply a partial update, and say what came of it."""
    profile = _require_profile(user)
    if _awaits_validation(user):
        raise WriteError(409, "An earlier change of your profile awaits validation.")
    type_id = data.get("type", profile.profile_id)
    survey = _survey(type_id)
    fields = profile_fields(survey)
    stored = member_answers(user)
    before = read_answers(fields, stored)
    changes, errors = check_answers(fields, before, data.get("answers", {}))
    if type_id != profile.profile_id:
        for name in missing_answers(fields, {**before, **changes}):
            errors.setdefault(name, ["is required"])
    if errors:
        raise WriteError(422, "Some answers are not accepted.", errors)

    organisation = _organisation_name(survey, {**before, **changes})
    if is_kept_by_business_wall(user, organisation):
        raise WriteError(
            409, "A Business Wall keeps you in your organisation: it cannot change."
        )
    moderated = [field.name for field in fields if field.moderated]
    report = {
        "changed": [*changes],
        "type_changed": type_id != profile.profile_id,
        "organisation_name": organisation,
        "awaiting_validation": any(name in changes for name in moderated),
        "dry_run": dry_run,
    }
    if dry_run or not (changes or report["type_changed"]):
        return report
    if update_member(user, type_id, {**stored, **changes}):
        db.session.rollback()
        raise WriteError(409, "The site could not save the profile.")
    return report


def profile_fields(survey: SurveyProfile) -> list[AnswerField]:
    return [
        answer_field
        for group in survey.groups
        for field, code in group.survey_fields
        for answer_field in _answer_fields(field, group.label, required=code == "M")
    ]


def _answer_fields(
    field: SurveyField, section: str, *, required: bool
) -> Iterator[AnswerField]:
    field_type = field.type if field.type in ONTOLOGY_MAP else field.type.lower()
    prefix = field_type if field_type in _TEXTS else field_type.partition("_")[0]
    if field_type in NOT_EDITABLE:
        return
    label = str(Markup(field.description).striptags())
    detail_label = ""
    if prefix in _DOUBLE:
        label, _, detail_label = label.partition(";")
    common: dict[str, Any] = {
        "name": field.name,
        "label": label.strip(),
        "section": section,
        "required": required,
        "moderated": field.validate_changes,
    }
    detail = {
        "name": f"{field.name}{DETAIL}",
        "label": detail_label.strip(),
        "section": section,
        "parent": field.name,
    }
    vocabulary = ONTOLOGY_MAP.get(field_type, "")
    match prefix:
        case "boolean":
            yield AnswerField(kind=Kind.FLAG, **common)
        case "list":
            yield AnswerField(kind=Kind.CHOICE, vocabulary=vocabulary, **common)
        case "multi":
            yield AnswerField(kind=Kind.CHOICES, vocabulary=vocabulary, **common)
        # The names of organisations, which the member may add to.
        case "listfree":
            yield AnswerField(kind=Kind.TEXT, max_length=_MAX_NAME, **common)
        case "multifree":
            yield AnswerField(kind=Kind.CHOICES, **common)
        case "multidual":
            groups = f"{vocabulary}{GROUPS}"
            yield AnswerField(kind=Kind.CHOICES, vocabulary=groups, **common)
            yield AnswerField(kind=Kind.CHOICES, vocabulary=vocabulary, **detail)
        case "country":
            yield AnswerField(kind=Kind.CHOICE, vocabulary=COUNTRIES, **common)
            # The form stores the city as a list.
            yield AnswerField(
                kind=Kind.CHOICES, vocabulary=CITIES, max_items=1, **detail
            )
        case _:
            yield AnswerField(kind=Kind.TEXT, **common, **_TEXTS[prefix])


def _require_profile(user: User) -> KYCProfile:
    if user.profile is None or not user.profile.profile_id:
        raise WriteError(409, "Your account has no profile yet: fill the form first.")
    return user.profile


def _survey(type_id: str) -> SurveyProfile:
    if type_id not in get_survey_profile_ids():
        raise WriteError(422, f"type: {type_id!r} is not a type of profile.")
    return get_survey_profile(type_id)


def _organisation_name(survey: SurveyProfile, answers: Answers) -> str:
    value = answers.get(survey.organisation_field, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return value


def _awaits_validation(user: User) -> bool:
    stmt = sa.select(User.id).where(
        User.is_clone.is_(True),
        User.cloned_user_id == user.id,
        User.deleted_at.is_(None),
    )
    return db.session.scalar(stmt.limit(1)) is not None
