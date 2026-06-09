# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for two pure properties on the BusinessWall ORM model.

These tests pin the *contract* of two getter properties that contain
non-trivial pure logic:

- ``BusinessWall.name_safe`` — a fallback chain that resolves a display
  name (own ``name`` → ``Organisation.bw_name`` → ``Organisation.name``
  → empty string).  This guarantees that templates and notifications
  always have *something* to show, even when fixture data is incomplete.

- ``BusinessWall.formatted_address`` — joins the four address fields
  (``postal_address``, ``code_postal``, ``ville``, ``pays_zip_ville``)
  into a single comma-separated string, skipping falsy fields.  This is
  the canonical postal-address renderer used in the BW UI.

Both properties are tested by *constructing* an unsaved ``BusinessWall``
(no session, no DB) — the SQLA mapped columns become ordinary attributes
when assigned after ``__init__``.  For the ``Organisation`` fallback in
``name_safe`` we monkey-patch ``get_organisation`` on the *instance* with
a duck-typed ``SimpleNamespace`` rather than spinning up a real DB.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.bw.bw_activation.models.business_wall import BusinessWall


def _make_bw(**overrides: object) -> BusinessWall:
    """Build a bare BusinessWall and assign explicit attribute overrides.

    Calling ``BusinessWall()`` produces an unsaved instance with all
    column defaults applied lazily by SQLAlchemy.  Because no session is
    attached, ``get_organisation()`` returns ``None`` unless we override
    it on the instance.  Helper centralises this setup so tests stay
    focused on assertions.
    """
    bw = BusinessWall()
    for attr, value in overrides.items():
        setattr(bw, attr, value)
    return bw


class TestNameSafe:
    """Pin the fallback chain of ``BusinessWall.name_safe``.

    The contract: prefer the BW's own ``name``; otherwise consult the
    linked ``Organisation`` (``bw_name`` first, then ``name``); finally
    fall back to ``""``.  Crucially the property must never raise nor
    return ``None`` — callers rely on a string for f-string rendering.
    """

    def test_returns_own_name_when_set(self):
        """Own ``name`` wins over any organisation lookup."""
        bw = _make_bw(name="Direct Name")
        # Sabotage get_organisation to prove it is *not* consulted when
        # the BW already has a name.
        bw.get_organisation = lambda: pytest.fail(  # type: ignore[method-assign]
            "get_organisation must not be called when self.name is set"
        )

        assert bw.name_safe == "Direct Name"

    def test_falls_back_to_org_bw_name_when_own_name_empty_string(self):
        """Empty-string ``name`` triggers the organisation lookup."""
        bw = _make_bw(name="")
        bw.get_organisation = lambda: SimpleNamespace(  # type: ignore[method-assign]
            bw_name="BW Brand", name="Legal Entity"
        )

        assert bw.name_safe == "BW Brand"

    def test_falls_back_to_org_bw_name_when_own_name_is_none(self):
        """``None`` ``name`` (nullable column) also triggers the lookup."""
        bw = _make_bw(name=None)
        bw.get_organisation = lambda: SimpleNamespace(  # type: ignore[method-assign]
            bw_name="BW Brand", name="Legal Entity"
        )

        assert bw.name_safe == "BW Brand"

    def test_falls_through_bw_name_to_org_name(self):
        """If ``org.bw_name`` is falsy, the property falls through to
        ``org.name`` — the legal/Organisation display name."""
        bw = _make_bw(name="")
        bw.get_organisation = lambda: SimpleNamespace(  # type: ignore[method-assign]
            bw_name="", name="Legal Entity"
        )

        assert bw.name_safe == "Legal Entity"

    def test_falls_through_bw_name_to_org_name_when_bw_name_none(self):
        """``None`` ``org.bw_name`` is treated the same as empty string."""
        bw = _make_bw(name="")
        bw.get_organisation = lambda: SimpleNamespace(  # type: ignore[method-assign]
            bw_name=None, name="Legal Entity"
        )

        assert bw.name_safe == "Legal Entity"

    def test_returns_empty_string_when_everything_empty(self):
        """All sources empty → empty string (never ``None``)."""
        bw = _make_bw(name="")
        bw.get_organisation = lambda: SimpleNamespace(  # type: ignore[method-assign]
            bw_name="", name=""
        )

        assert bw.name_safe == ""

    def test_returns_empty_string_when_org_missing(self):
        """No linked organisation → fall back to empty string.

        ``get_organisation`` returns ``None`` when there is no session
        attached (the default for an unsaved instance), so we exercise
        that real branch here without any monkey-patch.
        """
        bw = _make_bw(name=None)

        assert bw.name_safe == ""

    def test_returns_empty_string_when_org_has_no_name_fields(self):
        """Organisation present but both name fields empty → ``""``."""
        bw = _make_bw(name="")
        bw.get_organisation = lambda: SimpleNamespace(  # type: ignore[method-assign]
            bw_name=None, name=None
        )

        assert bw.name_safe == ""

    def test_result_is_always_a_string(self):
        """Contract guarantee: ``name_safe`` returns ``str`` even when
        the underlying ``name`` column is ``None``."""
        bw = _make_bw(name=None)

        result = bw.name_safe

        assert isinstance(result, str)


class TestFormattedAddress:
    """Pin the address-joining logic of ``BusinessWall.formatted_address``.

    The contract: join the four address fields with ``", "``, skipping
    any field that is falsy (``""`` or ``None``).  Order is fixed:
    street, postal code, city, country.  The result is always a string
    — never ``None`` — so templates can render it unconditionally.
    """

    def test_full_address_renders_all_four_fields_in_order(self):
        """All fields populated → ``street, zip, city, country``."""
        bw = _make_bw(
            postal_address="1 rue de Paris",
            code_postal="75001",
            ville="Paris",
            pays_zip_ville="FRA",
        )

        assert bw.formatted_address == "1 rue de Paris, 75001, Paris, FRA"

    def test_empty_instance_renders_empty_string(self):
        """Fresh ``BusinessWall()`` (all defaults) → ``""``."""
        bw = _make_bw()

        assert bw.formatted_address == ""

    def test_skips_empty_string_fields(self):
        """Empty-string fields are silently dropped from the join."""
        bw = _make_bw(
            postal_address="42 Main St",
            code_postal="",
            ville="London",
            pays_zip_ville="",
        )

        assert bw.formatted_address == "42 Main St, London"

    def test_skips_none_fields(self):
        """``code_postal`` and ``ville`` are nullable columns — ``None``
        values must be skipped, not rendered as ``"None"``."""
        bw = _make_bw(
            postal_address="42 Main St",
            code_postal=None,
            ville=None,
            pays_zip_ville="GBR",
        )

        assert bw.formatted_address == "42 Main St, GBR"

    def test_only_country_renders_just_the_country(self):
        """A degenerate case used by the BW UI when only the country is
        known — must not produce stray commas."""
        bw = _make_bw(pays_zip_ville="DEU")

        assert bw.formatted_address == "DEU"

    def test_only_middle_fields_renders_without_leading_or_trailing_comma(self):
        """Skipping the first and last field must not leave dangling
        separators."""
        bw = _make_bw(code_postal="10115", ville="Berlin")

        assert bw.formatted_address == "10115, Berlin"

    @pytest.mark.parametrize(
        ("fields", "expected"),
        [
            (
                {
                    "postal_address": "1 rue",
                    "code_postal": "75001",
                    "ville": "Paris",
                    "pays_zip_ville": "FRA",
                },
                "1 rue, 75001, Paris, FRA",
            ),
            (
                {
                    "postal_address": "1 rue",
                    "code_postal": "",
                    "ville": "Paris",
                    "pays_zip_ville": "FRA",
                },
                "1 rue, Paris, FRA",
            ),
            (
                {
                    "postal_address": "",
                    "code_postal": "75001",
                    "ville": "",
                    "pays_zip_ville": "FRA",
                },
                "75001, FRA",
            ),
            (
                {
                    "postal_address": "",
                    "code_postal": "",
                    "ville": "",
                    "pays_zip_ville": "",
                },
                "",
            ),
        ],
    )
    def test_parametrized_combinations(self, fields: dict[str, str], expected: str):
        """Cover the cartesian product of empty/present fields to lock
        the join behaviour at every position in the chain."""
        bw = _make_bw(**fields)

        assert bw.formatted_address == expected

    def test_result_is_always_a_string(self):
        """Contract guarantee: ``formatted_address`` returns ``str``."""
        bw = _make_bw()

        assert isinstance(bw.formatted_address, str)

    def test_does_not_mutate_underlying_fields(self):
        """The property is pure — reading it must not change state."""
        bw = _make_bw(
            postal_address="1 rue",
            code_postal="75001",
            ville="Paris",
            pays_zip_ville="FRA",
        )

        _ = bw.formatted_address
        _ = bw.formatted_address

        assert bw.postal_address == "1 rue"
        assert bw.code_postal == "75001"
        assert bw.ville == "Paris"
        assert bw.pays_zip_ville == "FRA"
