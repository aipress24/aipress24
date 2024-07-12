# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from typing import Any

from flask_wtf import FlaskForm
from markupsafe import Markup
from wtforms import (
    BooleanField,
    Field,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField,
    validators,
)

from .lib.country_select import CountrySelectField
from .lib.dual_select_multi import DualSelectField
from .lib.select_multi_optgroup import SelectMultiOptgroupField
from .lib.select_multi_simple import SelectMultiSimpleField
from .lib.select_multi_simple_free import SelectMultiSimpleFreeField
from .lib.select_one import SelectOneField
from .lib.select_one_free import SelectOneFreeField
from .lib.valid_email import ValidEmail
from .lib.valid_image import ValidImageField
from .lib.valid_password import ValidPassword
from .lib.valid_tel import ValidTel
from .lib.valid_url import ValidURL
from .ontologies import get_choices
from .survey_dataclass import Field as ParserField
from .survey_dataclass import Profile
from .temporary_blob import pop_tmp_blob

MAX_TEXTAREA = 1500
TAG_AREA_SIZE = f"(maximum {MAX_TEXTAREA} caractères)"
TAG_FREE_ELEMENT = "(vous pouvez ajouter un nouvel élément à la liste proposée)"
TAG_MANDATORY = "(*)"
TAG_MANY_CHOICES = "(plusieurs choix possibles)"
TAG_PHOTO_FORMAT = "(format JPG, PNG ou PDF, taille maximum de 2MB)"
TAG_LABELS = (
    TAG_AREA_SIZE,
    TAG_FREE_ELEMENT,
    TAG_MANDATORY,
    TAG_MANY_CHOICES,
    TAG_PHOTO_FORMAT,
)


def _filter_mandatory_label(description: str, code: str) -> str:
    if code == "M":
        return f"{description} {TAG_MANDATORY}"
    return description


def _filter_many_choices(description: str) -> str:
    return f"{description} {TAG_MANY_CHOICES}"


def _filter_max_textarea_size(description: str) -> str:
    return f"{description} {TAG_AREA_SIZE}"


def _filter_photo_format(description: str) -> str:
    return f"{description} {TAG_PHOTO_FORMAT}"


def _filter_mandatory_label_free(description: str, code: str) -> str:
    new_desc = f"{description} {TAG_FREE_ELEMENT}"
    return _filter_mandatory_label(new_desc, code)


def _is_required(code: str) -> bool:
    return code == "M"


def _filter_mandatory_validator(code: str) -> list:
    if _is_required(code):
        return [validators.InputRequired()]
    return [validators.Optional()]


def custom_bool_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = [validators.Optional()]
    code = ""
    return BooleanField(
        name=field.name,
        label=Markup(field.description),
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "boolean",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def _get_part(strlist: list[str], idx: int) -> str:
    try:
        return strlist[idx].strip()
    except IndexError:
        return ""


def custom_bool_link_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = [validators.Optional()]
    code = ""
    parts = field.description.split(";")
    message = _get_part(parts, 0)
    url = _get_part(parts, 1)
    ref = _get_part(parts, 2)
    label = f'{message} <a href="{url}" target="_blank">{ref}</a>'
    return BooleanField(
        name=field.name,
        label=Markup(label),
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "boolean",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_string_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = _filter_mandatory_validator(code)
    validators_list.append(validators.Length(max=80))
    return StringField(
        name=field.name,
        label=_filter_mandatory_label(field.description, code),
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_photo_field(field: ParserField, code: str, param: str = "") -> Field:
    # validators_list = _filter_mandatory_validator(code)
    label = _filter_photo_format(field.description)
    label = _filter_mandatory_label(label, code)
    return ValidImageField(
        name=field.name,
        label=label,
        id=field.id,
        # validators=validators_list,
        is_required=_is_required(code),
        render_kw={
            "kyc_type": "photo",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_email_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = _filter_mandatory_validator(code)
    validators_list.append(validators.Email())
    return ValidEmail(
        name=field.name,
        label=_filter_mandatory_label(field.description, code),
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "email",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_tel_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = _filter_mandatory_validator(code)
    validators_list.append(validators.Length(max=20))
    return ValidTel(
        name=field.name,
        label=_filter_mandatory_label(field.description, code),
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "tel",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_password_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = _filter_mandatory_validator(code)
    return ValidPassword(
        name=field.name,
        label=_filter_mandatory_label(field.description, code),
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "password",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_postcode_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = _filter_mandatory_validator(code)
    validators_list.append(validators.Length(max=80))
    return StringField(
        name=field.name,
        label=_filter_mandatory_label(field.description, code),
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "postcode",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_url_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = _filter_mandatory_validator(code)
    validators_list.append(validators.Length(max=80))
    return ValidURL(
        name=field.name,
        label=_filter_mandatory_label(field.description, code),
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "url",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_textarea_field(field: ParserField, code: str, param: str = "") -> Field:
    validators_list = _filter_mandatory_validator(code)
    validators_list.append(validators.Length(max=MAX_TEXTAREA))
    label = _filter_max_textarea_size(field.description)
    label = _filter_mandatory_label(label, code)
    return TextAreaField(
        name=field.name,
        label=label,
        id=field.id,
        validators=validators_list,
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def _fake_ontology_ajax(param: str) -> list[tuple]:
    choices: list[tuple[str, str]] = [("", f"Choisissez un parmi '{param}'")]
    for idx in range(1, 21):
        # choices.append((f"c{idx}", f"'{param}' {idx}"))  # type:ignore
        value = f"'{param}' {idx}"
        choices.append((value, value))
    return choices


def custom_list_field(field: ParserField, code: str, param: str) -> Field:
    validators_list = _filter_mandatory_validator(code)
    return SelectOneField(
        name=field.name,
        label=_filter_mandatory_label(field.description, code),
        id=field.id,
        choices=get_choices(param),
        validators=validators_list,
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_country_field(field: ParserField, code: str, param: str) -> Field:
    validators_list = _filter_mandatory_validator(code)
    label, _, label2 = field.description.partition(";")
    label = label.strip()
    label2 = label2.strip()
    return CountrySelectField(
        name=field.name,
        name2=f"{field.name}_detail",
        label=_filter_mandatory_label(label, code),
        id=field.id,
        id2=f"{field.id}_detail",
        label2=_filter_mandatory_label(label2, code),
        choices=get_choices(param),
        validators=validators_list,
        validate_choice=False,
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_list_free_field(field: ParserField, code: str, param: str) -> Field:
    """This list allows a free text for content not in the proposed list."""
    return SelectOneFreeField(
        name=field.name,
        label=_filter_mandatory_label_free(field.description, code),
        id=field.id,
        choices=get_choices(param),
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_ajax_field(field: ParserField, code: str, param: str) -> Field:
    # TODO: load ontology
    choices = _fake_ontology_ajax(param)

    validators_list = _filter_mandatory_validator(code)
    return SelectField(
        name=field.name,
        label=_filter_mandatory_label(field.description, code),
        id=field.id,
        choices=choices,
        validators=validators_list,
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_multi_free_field(field: ParserField, code: str, param: str) -> Field:
    # there is no "optgroup" version for multiple/free
    return _custom_multi_free_field_simple(field, code, param)


def custom_multi_field(field: ParserField, code: str, param: str) -> Field:
    if isinstance(get_choices(param), list):
        return _custom_multi_field_simple(field, code, param)
    return _custom_multi_field_optgroup(field, code, param)


def _custom_multi_field_simple(field: ParserField, code: str, param: str) -> Field:
    validators_list = _filter_mandatory_validator(code)  # buggy?
    label = _filter_many_choices(field.description)
    label = _filter_mandatory_label(label, code)
    return SelectMultiSimpleField(
        name=field.name,
        label=label,
        id=field.id,
        choices=get_choices(param),
        validators=validators_list,
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def _custom_multi_free_field_simple(field: ParserField, code: str, param: str) -> Field:
    validators_list = _filter_mandatory_validator(code)
    label = _filter_many_choices(field.description)
    label = _filter_mandatory_label(label, code)
    return SelectMultiSimpleFreeField(
        name=field.name,
        label=label,
        id=field.id,
        validate_choice=False,
        validators=validators_list,
        choices=get_choices(param),
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def _custom_multi_field_optgroup(field: ParserField, code: str, param: str) -> Field:
    validators_list = _filter_mandatory_validator(code)  # buggy?
    label = _filter_many_choices(field.description)
    label = _filter_mandatory_label(label, code)
    return SelectMultiOptgroupField(
        name=field.name,
        label=label,
        id=field.id,
        choices=get_choices(param),
        validators=validators_list,
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_dual_multi_field(field: ParserField, code: str, param: str) -> Field:
    #  {'Associations': ['Actions humanitaires', 'Communication et sensibilisatio ...
    validators_list = _filter_mandatory_validator(code)
    label, _, label2 = field.description.partition(";")
    label = _filter_many_choices(label.strip())
    label = _filter_mandatory_label(label, code)
    label2 = _filter_many_choices(label2.strip())
    label2 = _filter_mandatory_label(label2, code)
    return DualSelectField(
        name=field.name,
        name2=f"{field.name}_detail",
        label=label,
        id=field.id,
        id2=f"{field.id}_detail",
        label2=label2,
        choices=get_choices(param),
        # validators=validators_list,
        validate_choice=False,
        validators=validators_list,
        render_kw={
            "kyc_type": "string",
            "kyc_code": code,
            "kyc_message": field.upper_message,
        },
    )


def custom_multi_opt_field(
    field: ParserField, mandatory_flag: str, param: str
) -> Field:
    choices = get_choices(param)
    validators_list = _filter_mandatory_validator(mandatory_flag)
    label = _filter_many_choices(field.description)
    label = _filter_mandatory_label(label, mandatory_flag)
    return SelectMultipleField(
        name=field.name,
        label=label,
        id=field.id,
        choices=choices,
        validators=validators_list,
        render_kw={
            "kyc_type": "string",
            "kyc_code": mandatory_flag,
            "kyc_message": field.upper_message,
        },
    )


FIELD_TYPE_SELECTOR: Mapping[str, Callable] = {
    "boolean": custom_bool_field,
    "boolink": custom_bool_link_field,
    "string": custom_string_field,
    "textarea": custom_textarea_field,
    "photo": custom_photo_field,
    "email": custom_email_field,
    "tel": custom_tel_field,
    "password": custom_password_field,
    "postcode": custom_postcode_field,
    "url": custom_url_field,
    "list": custom_list_field,
    "listfree": custom_list_free_field,  # currently unused
    "multifree": custom_multi_free_field,  # used only for 'newsrooms'
    "multi": custom_multi_field,
    "multidual": custom_dual_multi_field,
    "multiopt": custom_multi_opt_field,
    "long": custom_ajax_field,
    "country": custom_country_field,
}

ring_class = "ring-1 ring-inset ring-gray-300"
focus_class = "focus:ring-2 focus:ring-inset focus:ring-indigo-600"


def _split_profile_field(field_type: str) -> tuple[str, str]:
    name = field_type.lower().strip()
    prefix, _, suffix = name.partition("_")
    if prefix in {
        "list",
        "listfree",
        "multi",
        "multidual",
        "multifree",
        "long",
        "multiopt",
        "country",
    }:
        return prefix, suffix
    return name, ""


def _collect_managed_data(form: FlaskForm, form_data: dict[str, Any]) -> dict[str, Any]:
    managed_data: dict[str, Any] = {}
    for key, value in form_data.items():
        try:
            # this fails for *_detail fields (second field of custom list)
            wt_field = getattr(form, key)
        except AttributeError:
            continue
        if isinstance(wt_field, (CountrySelectField, DualSelectField)):
            # now apply also to second field *_detail, store as a tuple of 2 values
            managed_data[key] = (value, form_data.get(f"{key}_detail", []))
        elif isinstance(
            wt_field,
            (
                StringField,
                BooleanField,
                SelectField,
                TextAreaField,
                SelectMultipleField,
            ),
        ):
            managed_data[key] = value
        elif isinstance(wt_field, ValidImageField):
            photo_filename, _uuid, photo = pop_tmp_blob(value)
            managed_data[key] = (photo_filename, photo)
    # debug:
    # if managed_data:
    #     print(
    #         f"managed data: {managed_data}",
    #         file=sys.stderr,
    #     )
    return managed_data


def _fill_managed_data(form: FlaskForm, managed_data: dict[str, Any]) -> None:
    for key, value in managed_data.items():
        wt_field = getattr(form, key)
        if isinstance(wt_field, (CountrySelectField, DualSelectField)):
            # apply also to second field *_detail
            first, second = value
            wt_field.data = first
            wt_field.data2 = second
        elif isinstance(wt_field, ValidImageField):
            filename, data = value
            wt_field.load_data(data, filename)
        else:
            wt_field.data = value


def generate_form(
    profile: Profile,
    form_data: dict | None = None,
    mode_edition: bool = False,
) -> FlaskForm:
    """The form contains several Fields and sub titles information.

    Form.kyc_order = [
        (group1.label, [fieldname_1 fieldname_2, ...]),
        (group2.label, [fieldnam.., ])
    ]

    If edition is True, do not show fields for email and password.

    """

    no_edit_fields = {"email", "password"}

    class DynForm(FlaskForm):
        pass

    # if form_data:
    #     print("////// form_data ////////", form_data, file=sys.stderr)
    # else:
    if not form_data:
        form_data = {}
    kyc_order = []
    for group in profile.groups:
        group_ordered_fields = []
        for profile_field, code in group.fields:
            profile_key, _ = _split_profile_field(profile_field.type)
            if mode_edition and profile_key in no_edit_fields:
                continue
            # print(f"/// {profile_field} {profile_key}", file=sys.stderr)
            field_fct = FIELD_TYPE_SELECTOR.get(profile_key)
            # print(f"/// {profile_field} {profile_key} {field_fct}", file=sys.stderr)
            if not field_fct:  # until we provide all custom fields classes
                print(f"Missing Field definition for: {profile_key!r}", file=sys.stderr)
                continue
            group_ordered_fields.append(profile_field.name)
            field_widget = field_fct(profile_field, code, profile_field.type)
            setattr(DynForm, profile_field.name, field_widget)

        kyc_group = (group.label, group_ordered_fields)
        kyc_order.append(kyc_group)
    DynForm.size = 3
    DynForm.kyc_order = kyc_order
    DynForm.kyc_description = profile.description
    form = DynForm()
    managed_data = _collect_managed_data(form, form_data)
    _fill_managed_data(form, managed_data)
    return form
