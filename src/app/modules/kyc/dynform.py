# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from enum import StrEnum
from typing import Any

from advanced_alchemy.types import FileObject
from flask_wtf import FlaskForm
from loguru import logger
from markupsafe import Markup
from wtforms import (
    BooleanField,
    IntegerField,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField,
    validators,
)
from wtforms.fields.core import UnboundField

from .lib.country_select import CountrySelectField
from .lib.dual_select_multi import DualSelectField
from .lib.select_multi_optgroup import SelectMultiOptgroupField
from .lib.select_multi_simple import SelectMultiSimpleField
from .lib.select_multi_simple_free import SelectMultiSimpleFreeField
from .lib.select_one import SelectOneField
from .lib.select_one_free import SelectOneFreeField
from .lib.valid_email import ValidEmail
from .lib.valid_email_free import ValidEmailFree
from .lib.valid_image import ValidImageField
from .lib.valid_image_square import ValidImageFieldSquare
from .lib.valid_password import ValidPassword
from .lib.valid_tel import ValidTel
from .lib.valid_url import ValidURL
from .ontology_loader import get_choices
from .survey_dataclass import SurveyField, SurveyProfile

MAX_IMAGE_SIZE = 4096
MAX_INT = 999999
MAX_STRING = 80
MAX_TEL = 20
MAX_TEXTAREA = 1500
MAX_TEXTAREA300 = 300
TAG_AREA_SIZE = f"(maximum {MAX_TEXTAREA} signes)"
TAG_AREA300_SIZE = f"(maximum {MAX_TEXTAREA300} signes)"
TAG_FREE_ELEMENT = "(vous pouvez ajouter un nouvel élément à la liste proposée)"
TAG_MANDATORY = "(*)"
TAG_MANY_CHOICES = "(plusieurs choix possibles)"
TAG_PHOTO_FORMAT = "(format JPG ou PNG, taille maximum de 2MB)"
TAG_PUBLIC = "(information pouvant être publique)"
TAG_LABELS = (
    TAG_AREA_SIZE,
    TAG_AREA300_SIZE,
    TAG_FREE_ELEMENT,
    TAG_MANDATORY,
    TAG_MANY_CHOICES,
    TAG_PHOTO_FORMAT,
)


def _filter_public_info(description: str, public: bool) -> str:
    if public:
        return f"{description} {TAG_PUBLIC}"
    return description


def _filter_mandatory_label(description: str, code: str) -> str:
    if code == "M":
        return f"{description} {TAG_MANDATORY}"
    return description


def _filter_many_choices(description: str) -> str:
    return f"{description} {TAG_MANY_CHOICES}"


def _filter_max_textarea_size(description: str) -> str:
    return f"{description} {TAG_AREA_SIZE}"


def _filter_max_textarea300_size(description: str) -> str:
    return f"{description} {TAG_AREA300_SIZE}"


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


class ReadOnly(StrEnum):
    """How a widget is told it must not be edited — they disagree.

    The fields in `lib/` take a `readonly` constructor argument; stock
    WTForms fields only understand `render_kw`; a checkbox needs
    `disabled`, since HTML `readonly` does nothing to a checkbox.
    """

    WIDGET = "widget"
    RENDER_KW = "render_kw"
    DISABLED = "disabled"
    UNSUPPORTED = "unsupported"


def _get_part(strlist: list[str], idx: int) -> str:
    try:
        return strlist[idx].strip()
    except IndexError:
        return ""


def _fake_ontology_ajax(param: str) -> list[tuple]:
    choices: list[tuple[str, str]] = [("", f"Choisissez un parmi '{param}'")]
    for idx in range(1, 21):
        value = f"'{param}' {idx}"
        choices.append((value, value))
    return choices


def _label(
    field: SurveyField,
    mandatory_code: str,
    *,
    text: str | None = None,
    prefix_tag: Callable[[str], str] | None = None,
    many_choices: bool = False,
) -> str:
    """The visible label: size or format tag, then public, then choices, then (*)."""
    label = field.description if text is None else text
    if prefix_tag is not None:
        label = prefix_tag(label)
    label = _filter_public_info(label, field.public_maxi)
    if many_choices:
        label = _filter_many_choices(label)
    return _filter_mandatory_label(label, mandatory_code)


def _render_kw(
    field: SurveyField,
    kyc_type: str,
    mandatory_code: str,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The `kyc_*` attributes the KYC renderer and its Alpine widgets read."""
    render_kw: dict[str, Any] = dict(extra or {})
    render_kw |= {
        "kyc_type": kyc_type,
        "kyc_code": mandatory_code,
        "kyc_message": field.upper_message,
    }
    return render_kw


def _field_builder(
    widget: type,
    kyc_type: str = "string",
    *,
    extra_validators: Sequence[Any] = (),
    with_validators: bool = True,
    prefix_tag: Callable[[str], str] | None = None,
    many_choices: bool = False,
    render_kw_extra: Mapping[str, Any] | None = None,
    readonly_mode: ReadOnly = ReadOnly.WIDGET,
    choices: Callable[[str], Any] | None = None,
    validate_choice: bool | None = None,
) -> Callable[..., UnboundField]:
    """Bind one `kyc_type` to the widget that renders it.

    `readonly` blanks the mandatory code: a field nobody can fill in
    cannot be required.
    """

    def build(
        field: SurveyField,
        mandatory_code: str = "",
        param: str = "",
        readonly: bool = False,
        **kwargs,
    ) -> UnboundField:
        if readonly:
            mandatory_code = ""
        render_kw = _render_kw(field, kyc_type, mandatory_code, render_kw_extra)
        widget_kwargs: dict[str, Any] = {
            "name": field.name,
            "label": _label(
                field,
                mandatory_code,
                prefix_tag=prefix_tag,
                many_choices=many_choices,
            ),
            "id": field.id,
            "render_kw": render_kw,
        }
        if with_validators:
            widget_kwargs["validators"] = [
                *_filter_mandatory_validator(mandatory_code),
                *extra_validators,
            ]
        if choices is not None:
            widget_kwargs["choices"] = choices(param)
        if validate_choice is not None:
            widget_kwargs["validate_choice"] = validate_choice

        match readonly_mode:
            case ReadOnly.WIDGET:
                widget_kwargs["readonly"] = 1 if readonly else 0
            case ReadOnly.RENDER_KW if readonly:
                render_kw["readonly"] = True
            case ReadOnly.DISABLED if readonly:
                render_kw["disabled"] = ""

        return widget(**widget_kwargs)

    return build


def _bool_field(field: SurveyField, label: Markup, readonly: bool) -> UnboundField:
    """A checkbox, where the mandatory code means something else and is dropped."""
    render_kw: dict[str, Any] = {
        "kyc_type": "boolean",
        "kyc_code": "",
        "kyc_message": field.upper_message,
    }
    if readonly:
        render_kw["disabled"] = ""
    return BooleanField(
        name=field.name,
        label=label,
        id=field.id,
        validators=[validators.Optional()],
        render_kw=render_kw,
    )


def custom_bool_field(
    field: SurveyField,
    mandatory_code: str = "",
    param: str = "",
    readonly: bool = False,
    **kwargs,
) -> UnboundField:
    return _bool_field(field, Markup(field.description), readonly)


def custom_bool_link_field(
    field: SurveyField,
    mandatory_code: str = "",
    param: str = "",
    readonly: bool = False,
    **kwargs,
) -> UnboundField:
    """A checkbox whose label carries a link: `message; url; link text`."""
    parts = field.description.split(";")
    message = _get_part(parts, 0)
    url = _get_part(parts, 1)
    ref = _get_part(parts, 2)
    label = f'{message} <a href="{url}" target="_blank">{ref}</a>'
    return _bool_field(field, Markup(label), readonly)


def _photo_builder(widget: type, kyc_type: str) -> Callable[..., UnboundField]:
    """Image widgets carry their own validation, so no validator is passed."""

    def build(
        field: SurveyField,
        mandatory_code: str = "",
        param: str = "",
        readonly: bool = False,
        file_object: FileObject | None = None,
        **kwargs,
    ) -> UnboundField:
        if readonly:
            mandatory_code = ""
        return widget(
            name=field.name,
            label=_label(field, mandatory_code, prefix_tag=_filter_photo_format),
            id=field.id,
            is_required=_is_required(mandatory_code),
            render_kw=_render_kw(field, kyc_type, mandatory_code),
            readonly=1 if readonly else 0,
            max_image_size=MAX_IMAGE_SIZE,
            file_object=file_object,
        )

    return build


def _dual_builder(widget: type, *, many_choices: bool) -> Callable[..., UnboundField]:
    """Two bound selects — a country and its region, an activity and its detail.

    The description carries both labels, separated by a semicolon; only
    the first one is ever public.
    """

    def build(
        field: SurveyField,
        mandatory_code: str = "",
        param: str = "",
        readonly: bool = False,
        **kwargs,
    ) -> UnboundField:
        if readonly:
            mandatory_code = ""
        text, _, text2 = field.description.partition(";")
        label2 = text2.strip()
        if many_choices:
            label2 = _filter_many_choices(label2)
        return widget(
            name=field.name,
            name2=f"{field.name}_detail",
            label=_label(
                field,
                mandatory_code,
                text=text.strip(),
                many_choices=many_choices,
            ),
            id=field.id,
            id2=f"{field.id}_detail",
            label2=_filter_mandatory_label(label2, mandatory_code),
            choices=get_choices(param),
            validators=_filter_mandatory_validator(mandatory_code),
            validate_choice=False,
            render_kw=_render_kw(field, "string", mandatory_code),
            readonly=1 if readonly else 0,
        )

    return build


custom_string_field = _field_builder(
    StringField,
    extra_validators=[validators.Length(max=MAX_STRING)],
    readonly_mode=ReadOnly.RENDER_KW,
)
custom_postcode_field = _field_builder(
    StringField,
    "postcode",
    extra_validators=[validators.Length(max=MAX_STRING)],
    readonly_mode=ReadOnly.RENDER_KW,
)
custom_int_field = _field_builder(
    IntegerField,
    "int",
    extra_validators=[validators.NumberRange(min=0, max=MAX_INT)],
    readonly_mode=ReadOnly.RENDER_KW,
)
custom_textarea_field = _field_builder(
    TextAreaField,
    extra_validators=[validators.Length(max=MAX_TEXTAREA)],
    prefix_tag=_filter_max_textarea_size,
    render_kw_extra={"rows": "5", "maxlength": MAX_TEXTAREA},
    readonly_mode=ReadOnly.RENDER_KW,
)
custom_textarea300_field = _field_builder(
    TextAreaField,
    extra_validators=[validators.Length(max=MAX_TEXTAREA300)],
    prefix_tag=_filter_max_textarea300_size,
    render_kw_extra={"rows": "3", "maxlength": MAX_TEXTAREA300},
    readonly_mode=ReadOnly.RENDER_KW,
)
custom_email_field = _field_builder(
    ValidEmail, "email", extra_validators=[validators.Email()]
)
custom_email_free_field = _field_builder(
    ValidEmailFree, "email", extra_validators=[validators.Email()]
)
custom_tel_field = _field_builder(
    ValidTel, "tel", extra_validators=[validators.Length(max=MAX_TEL)]
)
custom_url_field = _field_builder(
    ValidURL, "url", extra_validators=[validators.Length(max=MAX_STRING)]
)
custom_password_field = _field_builder(ValidPassword, "password")
custom_photo_field_standard = _photo_builder(ValidImageField, "photo")
custom_photo_square_field = _photo_builder(ValidImageFieldSquare, "photo_square")
custom_list_field = _field_builder(SelectOneField, choices=get_choices)
custom_list_free_field = _field_builder(
    SelectOneFreeField,
    with_validators=False,
    choices=get_choices,
    # This widget exists to accept a value outside the list, which a
    # validated choice would reject.
    validate_choice=False,
)
custom_ajax_field = _field_builder(
    SelectField,
    choices=_fake_ontology_ajax,  # TODO: load the real ontology
    readonly_mode=ReadOnly.UNSUPPORTED,
)
custom_multi_opt_field = _field_builder(
    SelectMultipleField,
    many_choices=True,
    choices=get_choices,
    readonly_mode=ReadOnly.UNSUPPORTED,
)
custom_multi_free_field = _field_builder(
    SelectMultiSimpleFreeField,
    many_choices=True,
    choices=get_choices,
    validate_choice=False,
)
custom_country_field = _dual_builder(CountrySelectField, many_choices=False)
custom_dual_multi_field = _dual_builder(DualSelectField, many_choices=True)

# TODO: a required multi-select only checks that *something* was picked.
_multi_simple_field = _field_builder(
    SelectMultiSimpleField, many_choices=True, choices=get_choices
)
_multi_optgroup_field = _field_builder(
    SelectMultiOptgroupField, many_choices=True, choices=get_choices
)


def custom_multi_field(
    field: SurveyField,
    mandatory_code: str = "",
    param: str = "",
    readonly: bool = False,
    **kwargs,
) -> UnboundField:
    """Flat ontologies get a plain multi-select, nested ones an optgroup."""
    if isinstance(get_choices(param), list):
        return _multi_simple_field(field, mandatory_code, param, readonly, **kwargs)
    return _multi_optgroup_field(field, mandatory_code, param, readonly, **kwargs)


FIELD_TYPE_SELECTOR: Mapping[str, Callable] = {
    "boolean": custom_bool_field,
    "boolink": custom_bool_link_field,
    "string": custom_string_field,
    "textarea": custom_textarea_field,
    "textarea300": custom_textarea300_field,
    "photo_square": custom_photo_square_field,
    "photo": custom_photo_field_standard,
    "email": custom_email_field,
    "email_free": custom_email_free_field,
    "tel": custom_tel_field,
    "password": custom_password_field,
    "postcode": custom_postcode_field,
    "url": custom_url_field,
    "list": custom_list_field,
    "listfree": custom_list_free_field,  # used for nom_orga, nom_media_instit, nom_agence_rp
    "multifree": custom_multi_free_field,  # used only for 'orga_newsrooms' / nom_media
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
        if isinstance(wt_field, CountrySelectField | DualSelectField):
            # now apply also to second field *_detail, store as a tuple of 2 values
            managed_data[key] = (value, form_data.get(f"{key}_detail", []))
        elif isinstance(
            wt_field,
            StringField
            | BooleanField
            | SelectField
            | TextAreaField
            | SelectMultipleField,
        ):
            managed_data[key] = value
        elif isinstance(wt_field, ValidImageField | ValidImageFieldSquare):
            pass
    return managed_data


def _fill_managed_data(form: FlaskForm, managed_data: dict[str, Any]) -> None:
    for key, value in managed_data.items():
        wt_field = getattr(form, key)
        if isinstance(wt_field, CountrySelectField | DualSelectField):
            # apply also to second field *_detail
            first, second = value
            wt_field.data = first
            wt_field.data2 = second
        elif isinstance(wt_field, ValidImageField | ValidImageFieldSquare):
            pass
        else:
            wt_field.data = value


def generate_form(
    profile: SurveyProfile,
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

    if not form_data:
        form_data = {}
    kyc_order = []
    for group in profile.groups:
        group_ordered_fields = []
        for profile_field, code in group.survey_fields:
            profile_key, _ = _split_profile_field(profile_field.type)
            if mode_edition and profile_key in no_edit_fields:
                continue

            field_fct = FIELD_TYPE_SELECTOR.get(profile_key)
            if not field_fct:
                logger.warning(
                    "No widget for KYC field type {!r}, field {!r} is skipped",
                    profile_key,
                    profile_field.name,
                )
                continue
            group_ordered_fields.append(profile_field.name)
            extra_params = {}
            if profile_key in {"photo", "photo_square"}:
                extra_params["file_object"] = form_data.get(profile_field.name)

            field_widget = field_fct(
                profile_field, code, profile_field.type, **extra_params
            )
            setattr(DynForm, profile_field.name, field_widget)

        kyc_group = (group.label, group_ordered_fields)
        kyc_order.append(kyc_group)
    DynForm.size = 3
    DynForm.kyc_order = kyc_order
    DynForm.kyc_description = profile.description
    logger.debug("kyc_order: {}", kyc_order)
    form = DynForm()
    managed_data = _collect_managed_data(form, form_data)
    _fill_managed_data(form, managed_data)
    return form
