"""Specialized form fields for Business Wall form."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-onlyfrom __future__ import annotations

from __future__ import annotations

from typing import Any

from advanced_alchemy.types import FileObject

from .valid_bw_image import ValidBWImageField

TAG_MANDATORY = "(*)"
TAG_PHOTO_FORMAT = "(format JPG ou PNG, taille maximum de 4MB)"
TAG_LABELS = (
    TAG_MANDATORY,
    TAG_PHOTO_FORMAT,
)


def _filter_mandatory_label(description: str, code: bool) -> str:
    if code:
        return f"{description} {TAG_MANDATORY}"
    return description


def _filter_photo_format(description: str) -> str:
    return f"{description} {TAG_PHOTO_FORMAT}"


def custom_bw_logo_field(
    name: str,
    description: str,
    mandatory: bool = False,
    readonly: bool = False,
    file_object: FileObject | dict[str, Any] | None = None,
) -> Field:
    # FIXME: what's this supposed to do?
    # validators_list = _filter_mandatory_validator(mandatory)
    label = _filter_photo_format(description)
    label = _filter_mandatory_label(label, mandatory)
    render_kw: dict[str, Any] = {
        "kyc_type": "photo",
        "kyc_code": "M" if mandatory else "",
        # "kyc_message": field.upper_message,
    }
    return ValidBWImageField(
        id=name,
        name=name,
        label=label,
        is_required=mandatory,
        render_kw=render_kw,
        readonly=1 if readonly else 0,
        max_image_size=4096,
        file_object=file_object,
    )
