# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the dict-building helpers behind
``get_pending_pr_bw_info_list`` and ``get_current_pr_bw_info_list`` in
``app.modules.bw.bw_activation.utils``.

These two public functions are what the BW management dashboard reads
to render the « PR Agency partnerships » tables. Both used to be tiny
imperative loops that interleaved DB lookups (``bw_contact_name_email``,
which goes through ``db.session``) with dict construction. That made
them impossible to unit-test : every assertion had to spin up a Flask
app, a SQLAlchemy session, and seed users — for what is, in the end, a
pure dict-shape contract.

Pattern A (functional core / imperative shell) lets us pull the pure
parts out :

- ``_pending_bw_to_info_dict(bw, status, contact)`` — builds the 4-key
  dict for a pending partnership row.
- ``_current_bw_to_info_dict(bw, contact)`` — builds the 4-key dict for
  an active partnership row.

The imperative shell (the public ``get_*_info_list`` functions) is now
a 3-line orchestration wrapping each helper in a list comprehension.
That orchestration is covered by integration tests; here we lock in :

- the **exact key set** the dashboard template depends on,
- the human-readable **status translation** (« invitation en cours »,
  « invitation rejetée », « invitation expirée »),
- the **fallback** when the partnership status is unexpected — the
  raw status is returned so we never blow up on a `KeyError` and crash
  the dashboard page,
- that the BW ``id`` is **always stringified** (the dashboard URLs
  treat it as a string token), even when the underlying ``id`` is a
  UUID or an int,
- that the ``contact`` tuple is passed through **verbatim** — name in
  index 0, email in index 1, no swap.

We use plain stand-in classes (no mocking library, no fixture-based
attribute substitution) because the helpers are deliberately
attribute-driven : they read ``bw.name_safe`` and ``bw.id`` and nothing
else. A bare dataclass-like ``object`` is enough.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest

from app.modules.bw.bw_activation.utils import (
    _PENDING_STATUS_TRANSLATION,
    _current_bw_to_info_dict,
    _pending_bw_to_info_dict,
)

# --------------------------------------------------------------------- #
# Stand-ins — plain attribute carriers. The helpers only read
# `bw.name_safe` and `bw.id`, so we do NOT need a real SQLAlchemy
# mapped class, an Organisation, a User, a Flask app or a DB session.
# --------------------------------------------------------------------- #


@dataclass
class FakeBW:
    """Minimal stand-in for ``BusinessWall``.

    The two production helpers under test reach for exactly two
    attributes : ``name_safe`` (the display name, resolved by
    ``BusinessWall.name_safe`` with Organisation fallback) and ``id``
    (the BW primary key, normally a UUID). Anything else on the real
    class is irrelevant to the dict-shape contract.
    """

    name_safe: str
    id: object  # UUID, int, or str — the helper must stringify it.


# --------------------------------------------------------------------- #
# _pending_bw_to_info_dict
# --------------------------------------------------------------------- #


class TestPendingBwToInfoDictKeys:
    """The dashboard template iterates `row['bw_name']`, `row['bw_contact_name']`,
    `row['bw_contact_email']`, `row['bw_status']`. Pin the exact key set so
    a future « let's rename `bw_status` to `status` » breaks here, not in
    production rendering."""

    def test_returns_exactly_four_keys(self) -> None:
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=1))
        row = _pending_bw_to_info_dict(bw, "invited", ("Alice", "a@x.test"))

        assert set(row.keys()) == {
            "bw_name",
            "bw_contact_name",
            "bw_contact_email",
            "bw_status",
        }

    def test_no_bw_id_key_for_pending(self) -> None:
        # Pending rows do NOT expose `bw_id`: the dashboard does not link
        # to a partner BW until the partnership is accepted. Pin so the
        # « let's just add bw_id everywhere » refactor stays deliberate.
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=1))
        row = _pending_bw_to_info_dict(bw, "invited", ("Alice", "a@x.test"))

        assert "bw_id" not in row


class TestPendingBwToInfoDictValues:
    """Pin the value side of the contract : passthrough of name and
    contact, French translation of the status."""

    @pytest.mark.parametrize(
        ("status", "expected_label"),
        [
            ("invited", "invitation en cours"),
            ("rejected", "invitation rejetée"),
            ("expired", "invitation expirée"),
        ],
    )
    def test_status_is_translated_to_french_label(
        self, status: str, expected_label: str
    ) -> None:
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=1))
        row = _pending_bw_to_info_dict(bw, status, ("Alice", "a@x.test"))

        assert row["bw_status"] == expected_label

    def test_unknown_status_falls_back_to_raw_value(self) -> None:
        # The pre-refactor code did `TRANSLATION[bw_status[1]]` which
        # raised KeyError on an unexpected status (e.g. "active" leaking
        # in from a stale partnership row, or a new enum value added
        # without updating the map). The helper now falls back to the
        # raw status string so the dashboard never 500s on bad data.
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=1))
        row = _pending_bw_to_info_dict(bw, "active", ("Alice", "a@x.test"))

        assert row["bw_status"] == "active"

    def test_empty_status_falls_back_to_empty_string(self) -> None:
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=1))
        row = _pending_bw_to_info_dict(bw, "", ("Alice", "a@x.test"))

        assert row["bw_status"] == ""

    def test_bw_name_comes_from_name_safe_property(self) -> None:
        bw = FakeBW(name_safe="Org-Fallback-Name", id=UUID(int=2))
        row = _pending_bw_to_info_dict(bw, "invited", ("Alice", "a@x.test"))

        assert row["bw_name"] == "Org-Fallback-Name"

    def test_empty_name_safe_passes_through(self) -> None:
        # `BusinessWall.name_safe` returns "" when neither the BW nor its
        # Organisation has a name. The helper must not magic-fill it.
        bw = FakeBW(name_safe="", id=UUID(int=3))
        row = _pending_bw_to_info_dict(bw, "invited", ("Alice", "a@x.test"))

        assert row["bw_name"] == ""

    def test_contact_tuple_is_passed_through_in_order(self) -> None:
        # `bw_contact_name_email` returns (full_name, email). The helper
        # MUST NOT swap them — a swap would render emails as display
        # names in the dashboard and leak addresses everywhere.
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=4))
        row = _pending_bw_to_info_dict(
            bw, "invited", ("Alice Dupont", "alice@example.test")
        )

        assert row["bw_contact_name"] == "Alice Dupont"
        assert row["bw_contact_email"] == "alice@example.test"

    def test_empty_contact_strings_are_preserved(self) -> None:
        # If the owner has no full_name / email yet (newly created
        # account), the dict must still build — empty strings, not None.
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=5))
        row = _pending_bw_to_info_dict(bw, "invited", ("", ""))

        assert row["bw_contact_name"] == ""
        assert row["bw_contact_email"] == ""


class TestPendingStatusTranslationConstant:
    """The translation map is module-scope so the helper does not rebuild
    a dict on every iteration. Pin the visible UI labels so a typo in a
    French translation breaks here, not in a screenshot review."""

    def test_exact_keys(self) -> None:
        assert set(_PENDING_STATUS_TRANSLATION.keys()) == {
            "invited",
            "rejected",
            "expired",
        }

    def test_french_labels_verbatim(self) -> None:
        # Verbatim so accidental edits (capitalisation, accents,
        # spacing) are caught.
        assert _PENDING_STATUS_TRANSLATION["invited"] == "invitation en cours"
        assert _PENDING_STATUS_TRANSLATION["rejected"] == "invitation rejetée"
        assert _PENDING_STATUS_TRANSLATION["expired"] == "invitation expirée"


# --------------------------------------------------------------------- #
# _current_bw_to_info_dict
# --------------------------------------------------------------------- #


class TestCurrentBwToInfoDictKeys:
    """The active-partnership row carries `bw_id` (used to build the
    « manage this partnership » dashboard link) instead of `bw_status`.
    Pin the contract here."""

    def test_returns_exactly_four_keys(self) -> None:
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=10))
        row = _current_bw_to_info_dict(bw, ("Alice", "a@x.test"))

        assert set(row.keys()) == {
            "bw_name",
            "bw_contact_name",
            "bw_contact_email",
            "bw_id",
        }

    def test_no_bw_status_key_for_current(self) -> None:
        # Active rows never expose `bw_status`: the partnership is, by
        # definition, active — the dashboard does not need to render a
        # status badge. Pin to catch accidental key duplication.
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=10))
        row = _current_bw_to_info_dict(bw, ("Alice", "a@x.test"))

        assert "bw_status" not in row


class TestCurrentBwToInfoDictValues:
    """Pin the value contract for the active row, focusing on the
    bw_id stringification quirk and contact tuple passthrough."""

    def test_bw_id_is_stringified_from_uuid(self) -> None:
        # The dashboard URL helper interpolates `bw_id` as a string.
        # The helper does `str(bw.id)` so a UUID lands as its
        # canonical hex form.
        uuid_val = UUID("12345678-1234-5678-1234-567812345678")
        bw = FakeBW(name_safe="Acme PR", id=uuid_val)
        row = _current_bw_to_info_dict(bw, ("Alice", "a@x.test"))

        assert row["bw_id"] == "12345678-1234-5678-1234-567812345678"
        assert isinstance(row["bw_id"], str)

    @pytest.mark.parametrize(
        ("raw_id", "expected"),
        [
            (UUID(int=0), "00000000-0000-0000-0000-000000000000"),
            (42, "42"),  # legacy int IDs from very old BWs
            ("already-a-string", "already-a-string"),
        ],
    )
    def test_bw_id_stringification_for_various_id_types(
        self, raw_id: object, expected: str
    ) -> None:
        bw = FakeBW(name_safe="Acme PR", id=raw_id)
        row = _current_bw_to_info_dict(bw, ("Alice", "a@x.test"))

        assert row["bw_id"] == expected

    def test_bw_name_from_name_safe(self) -> None:
        bw = FakeBW(name_safe="My-Active-Partner", id=UUID(int=11))
        row = _current_bw_to_info_dict(bw, ("Alice", "a@x.test"))

        assert row["bw_name"] == "My-Active-Partner"

    def test_empty_name_safe_passes_through(self) -> None:
        bw = FakeBW(name_safe="", id=UUID(int=12))
        row = _current_bw_to_info_dict(bw, ("Alice", "a@x.test"))

        assert row["bw_name"] == ""

    def test_contact_tuple_is_passed_through_in_order(self) -> None:
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=13))
        row = _current_bw_to_info_dict(
            bw, ("Bob Martin", "bob@example.test")
        )

        assert row["bw_contact_name"] == "Bob Martin"
        assert row["bw_contact_email"] == "bob@example.test"

    def test_empty_contact_strings_are_preserved(self) -> None:
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=14))
        row = _current_bw_to_info_dict(bw, ("", ""))

        assert row["bw_contact_name"] == ""
        assert row["bw_contact_email"] == ""


# --------------------------------------------------------------------- #
# Cross-helper invariants
# --------------------------------------------------------------------- #


class TestPendingAndCurrentDictShapesAreDisjoint:
    """The two dict shapes share three keys (bw_name, bw_contact_name,
    bw_contact_email) and differ in exactly one (bw_status vs bw_id).
    Pin that invariant so a refactor that drifts the shapes (e.g.
    « let's always include bw_id ») breaks here."""

    def test_three_keys_are_shared(self) -> None:
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=20))
        pending = _pending_bw_to_info_dict(bw, "invited", ("A", "a@x.test"))
        current = _current_bw_to_info_dict(bw, ("A", "a@x.test"))

        shared = set(pending.keys()) & set(current.keys())
        assert shared == {"bw_name", "bw_contact_name", "bw_contact_email"}

    def test_one_key_differs(self) -> None:
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=21))
        pending = _pending_bw_to_info_dict(bw, "invited", ("A", "a@x.test"))
        current = _current_bw_to_info_dict(bw, ("A", "a@x.test"))

        only_pending = set(pending.keys()) - set(current.keys())
        only_current = set(current.keys()) - set(pending.keys())
        assert only_pending == {"bw_status"}
        assert only_current == {"bw_id"}

    def test_shared_keys_carry_identical_values_for_same_inputs(self) -> None:
        # The three shared keys (name + contact pair) MUST produce the
        # same values across both helpers for the same BW + contact —
        # the two views are over the same data source.
        bw = FakeBW(name_safe="Acme PR", id=UUID(int=22))
        contact = ("Carol", "carol@example.test")
        pending = _pending_bw_to_info_dict(bw, "invited", contact)
        current = _current_bw_to_info_dict(bw, contact)

        for key in ("bw_name", "bw_contact_name", "bw_contact_email"):
            assert pending[key] == current[key]
