# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Every entry of `FIELD_TYPE_SELECTOR`, checked uniformly.

The a_unit tests in `tests/a_unit/modules/kyc/test_dynform.py` go deep on
a dozen builders. This file goes wide instead: it states, once per
`kyc_type`, which widget must come out and how that widget is told it is
read-only — the three facts a mistyped table row gets wrong.

It sits at the b_integration tier because the choice-bearing builders
call `get_choices`, which reads taxonomies from the database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from wtforms import (
    BooleanField,
    SelectField,
    SelectMultipleField,
    StringField,
    TextAreaField,
)
from wtforms.fields.core import UnboundField

from app.modules.kyc.dynform import (
    FIELD_TYPE_SELECTOR,
    TAG_MANDATORY,
    ReadOnly,
)
from app.modules.kyc.lib.country_select import CountrySelectField
from app.modules.kyc.lib.dual_select_multi import DualSelectField
from app.modules.kyc.lib.select_multi_simple import SelectMultiSimpleField
from app.modules.kyc.lib.select_multi_simple_free import SelectMultiSimpleFreeField
from app.modules.kyc.lib.select_one import SelectOneField
from app.modules.kyc.lib.select_one_free import SelectOneFreeField
from app.modules.kyc.lib.valid_email import ValidEmail
from app.modules.kyc.lib.valid_email_free import ValidEmailFree
from app.modules.kyc.lib.valid_image import ValidImageField
from app.modules.kyc.lib.valid_image_square import ValidImageFieldSquare
from app.modules.kyc.lib.valid_password import ValidPassword
from app.modules.kyc.lib.valid_tel import ValidTel
from app.modules.kyc.lib.valid_url import ValidURL
from app.modules.kyc.ontology_loader import get_ontology_content
from app.modules.kyc.survey_dataclass import SurveyField
from app.services.taxonomies import TaxonomyEntry

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import Session

#: widget class, the `kyc_type` written into `render_kw`, and the
#: read-only convention. A new field type must be declared here too.
EXPECTED: dict[str, tuple[type, str, ReadOnly]] = {
    "boolean": (BooleanField, "boolean", ReadOnly.DISABLED),
    "boolink": (BooleanField, "boolean", ReadOnly.DISABLED),
    "string": (StringField, "string", ReadOnly.RENDER_KW),
    "postcode": (StringField, "postcode", ReadOnly.RENDER_KW),
    "textarea": (TextAreaField, "string", ReadOnly.RENDER_KW),
    "textarea300": (TextAreaField, "string", ReadOnly.RENDER_KW),
    "email": (ValidEmail, "email", ReadOnly.WIDGET),
    "email_free": (ValidEmailFree, "email", ReadOnly.WIDGET),
    "tel": (ValidTel, "tel", ReadOnly.WIDGET),
    "url": (ValidURL, "url", ReadOnly.WIDGET),
    "password": (ValidPassword, "password", ReadOnly.WIDGET),
    "photo": (ValidImageField, "photo", ReadOnly.WIDGET),
    "photo_square": (ValidImageFieldSquare, "photo_square", ReadOnly.WIDGET),
    "list": (SelectOneField, "string", ReadOnly.WIDGET),
    "listfree": (SelectOneFreeField, "string", ReadOnly.WIDGET),
    "multi": (SelectMultiSimpleField, "string", ReadOnly.WIDGET),
    "multifree": (SelectMultiSimpleFreeField, "string", ReadOnly.WIDGET),
    "multiopt": (SelectMultipleField, "string", ReadOnly.UNSUPPORTED),
    "multidual": (DualSelectField, "string", ReadOnly.WIDGET),
    "country": (CountrySelectField, "string", ReadOnly.WIDGET),
    "long": (SelectField, "string", ReadOnly.UNSUPPORTED),
}

#: A `param` each builder can resolve. `get_choices` is keyed by the full
#: field type, so these are types and not bare taxonomy names.
PARAM = {
    "list": "list_civilite",
    "listfree": "listfree_nom_orga",
    "multi": "multi_type_media",
    "multifree": "multifree_newsrooms",
    "multiopt": "multi_type_media",
    "multidual": "multidual_type_orga",
    "country": "country_pays",
}

#: The two checkbox types drop the mandatory code: it means something
#: else on a checkbox, so it reaches neither the label nor `render_kw`.
NO_MANDATORY_CODE = {"boolean", "boolink"}


@pytest.fixture(autouse=True)
def _seeded_taxonomies(db_session: Session) -> Iterator[None]:
    """The taxonomies the choice-bearing builders read, and a clean cache."""
    get_ontology_content.cache_clear()
    rows = [
        ("civilite", "", "Madame", 1),
        ("civilite", "", "Monsieur", 2),
        ("media_type", "", "Presse écrite", 1),
        ("type_organisation_detail", "Associations", "Humanitaire", 1),
        ("pays", "Europe", "France", 1),
    ]
    for taxonomy_name, category, value, seq in rows:
        db_session.add(
            TaxonomyEntry(
                taxonomy_name=taxonomy_name,
                name=value,
                category=category,
                value=value,
                seq=seq,
            )
        )
    db_session.flush()
    yield
    get_ontology_content.cache_clear()


def _build(type_name: str, mandatory_code: str, *, readonly: bool) -> UnboundField:
    field = SurveyField(
        id="fid",
        name="fname",
        # The semicolon splits the label for the two dual-select types.
        description="Une description; https://example.com; Réf",
        public_maxi=True,
        upper_message="msg",
    )
    builder = FIELD_TYPE_SELECTOR[type_name]
    param = PARAM.get(type_name, type_name)
    return builder(field, mandatory_code, param, readonly=readonly)


def test_every_field_type_states_its_expectation() -> None:
    """A new entry in the selector must be declared here as well."""
    assert set(FIELD_TYPE_SELECTOR) == set(EXPECTED)


@pytest.mark.parametrize("type_name", sorted(EXPECTED))
def test_builds_the_declared_widget(type_name: str) -> None:
    widget, kyc_type, _ = EXPECTED[type_name]

    unbound = _build(type_name, "M", readonly=False)

    assert isinstance(unbound, UnboundField)
    assert unbound.field_class is widget
    assert unbound.kwargs["render_kw"]["kyc_type"] == kyc_type
    assert unbound.kwargs["id"] == "fid"
    # `UnboundField` lifts `name` out of the kwargs onto itself.
    assert unbound.name == "fname"
    assert unbound.kwargs["render_kw"]["kyc_message"] == "msg"


@pytest.mark.parametrize("type_name", sorted(EXPECTED))
def test_readonly_reaches_the_widget(type_name: str) -> None:
    """Each widget family learns it is read-only in its own way."""
    _, _, mode = EXPECTED[type_name]

    render_kw = _build(type_name, "M", readonly=True).kwargs["render_kw"]
    editable = _build(type_name, "M", readonly=False)

    match mode:
        case ReadOnly.WIDGET:
            assert _build(type_name, "M", readonly=True).kwargs["readonly"] == 1
            assert editable.kwargs["readonly"] == 0
        case ReadOnly.RENDER_KW:
            assert render_kw["readonly"] is True
            assert "readonly" not in editable.kwargs["render_kw"]
        case ReadOnly.DISABLED:
            assert render_kw["disabled"] == ""
            assert "disabled" not in editable.kwargs["render_kw"]
        case ReadOnly.UNSUPPORTED:
            assert "readonly" not in render_kw
            assert "readonly" not in editable.kwargs


@pytest.mark.parametrize("type_name", sorted(EXPECTED))
def test_readonly_drops_the_mandatory_code(type_name: str) -> None:
    """Nobody can fill in a read-only field, so it cannot be required."""
    unbound = _build(type_name, "M", readonly=True)

    assert unbound.kwargs["render_kw"]["kyc_code"] == ""
    assert TAG_MANDATORY not in str(unbound.kwargs["label"])


@pytest.mark.parametrize("type_name", sorted(set(EXPECTED) - NO_MANDATORY_CODE))
def test_mandatory_code_marks_the_label(type_name: str) -> None:
    mandatory = _build(type_name, "M", readonly=False)
    optional = _build(type_name, "O", readonly=False)

    assert TAG_MANDATORY in str(mandatory.kwargs["label"])
    assert TAG_MANDATORY not in str(optional.kwargs["label"])
    assert mandatory.kwargs["render_kw"]["kyc_code"] == "M"
