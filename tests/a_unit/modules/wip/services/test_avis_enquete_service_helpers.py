# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers extracted from `avis_enquete_service`.

The service module orchestrates DB writes, e-mail sends and in-app
notifications for the « Avis d'Enquête » newsroom workflow — most of
its surface is genuinely DB-bound and lives at the b_integration tier.

To keep the unit tier honest, the orchestration methods had several
embedded pure pieces lifted out into module-level helpers (Pattern A) :

- RDV type / contact-info / date formatting used by the e-mail layer ;
- bw_name resolution (active BW → org → ``"inconnue"`` fallback) ;
- predicates and filters used by ciblage (resync, known experts,
  colleagues eligible for the « non-mais » suggestion path) ;
- the dedup-preserve-order helper that powers ``press_officer_emails`` ;
- the notification-message strings (a regression in the wording rides
  through every notification path silently — pin them here) ;
- the length-validation guard on ``notify_experts`` so a mismatch
  raises with a useful message.

Stand-in objects (``_FakeRDVType``, ``_FakeContact``, ``_FakeMember``)
keep the suite ORM-free. NO mocks, NO patches.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.wip.services.newsroom.avis_enquete_service import (
    _dedup_preserve_order,
    _filter_eligible_colleagues,
    _filter_unknown_experts,
    _format_notify_avis_message,
    _format_notify_rdv_accepted_message,
    _format_notify_rdv_proposed_message,
    _format_notify_rdv_refused_message,
    _format_proposed_slots,
    _format_rdv_contact_info,
    _format_rdv_datetime,
    _format_rdv_type_label,
    _format_suggested_message,
    _is_contact_removable,
    _resolve_bw_display_name,
    _validate_notify_lengths,
)

# ---------------------------------------------------------------------------
# Stand-ins — duck-typed so we don't pull SQLAlchemy / Flask into a unit suite
# ---------------------------------------------------------------------------


@dataclass
class _FakeRDVType:
    """Minimal stand-in for ``RDVType`` — the helpers only read ``.name``."""

    name: str


@dataclass
class _FakeUser:
    """Stand-in for ``app.models.auth.User`` for filter helpers."""

    id: int = 0
    active: bool = True


@dataclass
class _FakeContact:
    """Stand-in for ``ContactAvisEnquete`` for the resync predicate."""

    expert_id: int = 0
    status: Any = None
    rdv_status: Any = None
    suggested_by_user_id: int | None = None


@dataclass
class _Sentinel:
    """Used in place of ``StatutAvis.EN_ATTENTE`` and ``RDVStatus.NO_RDV``.

    Helpers compare via ``==`` ; any hashable object with a working
    equality (dataclass default) is fine — we don't need the real Enum.
    """

    name: str


EN_ATTENTE = _Sentinel("EN_ATTENTE")
NO_RDV = _Sentinel("NO_RDV")
OTHER_STATUS = _Sentinel("OTHER")


# ---------------------------------------------------------------------------
# _format_rdv_type_label
# ---------------------------------------------------------------------------


class TestFormatRdvTypeLabel:
    """E-mail templates print this string in the subject line ; a typo
    here ships to every expert who receives an RDV proposal."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("PHONE", "Rendez-vous téléphonique"),
            ("VIDEO", "Rendez-vous visioconférence"),
            ("F2F", "Rendez-vous face-à-face"),
        ],
    )
    def test_known_types(self, name: str, expected: str) -> None:
        assert _format_rdv_type_label(_FakeRDVType(name=name)) == expected

    def test_none_returns_empty(self) -> None:
        """Legacy rows can have ``rdv_type IS NULL`` — must not crash."""
        assert _format_rdv_type_label(None) == ""

    def test_unknown_name_returns_empty(self) -> None:
        """Defensive : a future RDVType value not yet mapped here must
        return ``""`` rather than raising KeyError — same contract as
        the legacy if/elif/else chain."""
        assert _format_rdv_type_label(_FakeRDVType(name="UNKNOWN")) == ""

    def test_object_without_name_returns_empty(self) -> None:
        class _Bare:
            pass

        assert _format_rdv_type_label(_Bare()) == ""


# ---------------------------------------------------------------------------
# _format_rdv_contact_info
# ---------------------------------------------------------------------------


class TestFormatRdvContactInfo:
    """The contact info line tells the expert where / how to reach the
    journalist. Wrong line → silent loss of the meeting."""

    def test_phone_uses_phone_field(self) -> None:
        info = _format_rdv_contact_info(
            _FakeRDVType(name="PHONE"),
            phone="+33 6 12",
            video_link="ignored",
            address="ignored",
        )
        assert info == "Numéro de téléphone: +33 6 12"

    def test_video_uses_video_link(self) -> None:
        info = _format_rdv_contact_info(
            _FakeRDVType(name="VIDEO"),
            phone="ignored",
            video_link="https://meet.example",
            address="ignored",
        )
        assert info == "Lien visioconférence: https://meet.example"

    def test_f2f_uses_address(self) -> None:
        info = _format_rdv_contact_info(
            _FakeRDVType(name="F2F"),
            phone="ignored",
            video_link="ignored",
            address="1 rue de la Paix",
        )
        assert info == "Adresse: 1 rue de la Paix"

    def test_none_returns_empty(self) -> None:
        assert _format_rdv_contact_info(None, phone="x") == ""

    def test_unknown_returns_empty(self) -> None:
        assert _format_rdv_contact_info(_FakeRDVType(name="OTHER")) == ""

    def test_phone_with_empty_field_keeps_label(self) -> None:
        """The label is rendered even when the value is empty so a
        misconfigured contact still shows up as 'phone but no number',
        not as 'unknown RDV type'. Mirrors the legacy behaviour."""
        assert (
            _format_rdv_contact_info(_FakeRDVType(name="PHONE"))
            == "Numéro de téléphone: "
        )


# ---------------------------------------------------------------------------
# _format_rdv_datetime / _format_proposed_slots
# ---------------------------------------------------------------------------


class TestFormatRdvDatetime:
    def test_canonical_format(self) -> None:
        dt = datetime(2026, 6, 10, 14, 30, tzinfo=UTC)
        assert _format_rdv_datetime(dt) == "10/06/2026 à 14:30"

    def test_none_returns_empty(self) -> None:
        assert _format_rdv_datetime(None) == ""

    def test_pads_single_digits(self) -> None:
        dt = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
        assert _format_rdv_datetime(dt) == "02/01/2026 à 03:04"


class TestFormatProposedSlots:
    def test_empty_iterable(self) -> None:
        assert _format_proposed_slots([]) == []

    def test_preserves_order(self) -> None:
        slots = [
            datetime(2026, 6, 10, 9, 0, tzinfo=UTC),
            datetime(2026, 6, 11, 14, 30, tzinfo=UTC),
        ]
        assert _format_proposed_slots(slots) == [
            "10/06/2026 à 09:00",
            "11/06/2026 à 14:30",
        ]


# ---------------------------------------------------------------------------
# _dedup_preserve_order
# ---------------------------------------------------------------------------


class TestDedupPreserveOrder:
    """Order matters : internal BWPRi first, then external agency
    owners — see press_officer_emails docstring."""

    def test_empty_input(self) -> None:
        assert _dedup_preserve_order([]) == []

    def test_no_duplicates_keeps_order(self) -> None:
        assert _dedup_preserve_order(["a", "b", "c"]) == ["a", "b", "c"]

    def test_duplicates_dropped_first_seen_wins(self) -> None:
        assert _dedup_preserve_order(["a", "b", "a", "c", "b"]) == [
            "a",
            "b",
            "c",
        ]

    def test_falsy_entries_dropped(self) -> None:
        """An empty BW role assignment leaves an empty string in the
        pipeline — the dedup helper must drop it so we never send to
        ``""`` (which would crash the SMTP layer)."""
        assert _dedup_preserve_order(["a", "", "b", ""]) == ["a", "b"]


# ---------------------------------------------------------------------------
# _resolve_bw_display_name
# ---------------------------------------------------------------------------


class TestResolveBwDisplayName:
    """Media-group case (LVMH owns Les Échos) : the expert expects to
    see 'Les Échos', not 'LVMH'. Active BW wins ; org is the fallback ;
    'inconnue' is the last resort so the e-mail template never
    interpolates an empty string."""

    def test_active_bw_name_wins(self) -> None:
        assert _resolve_bw_display_name("Les Échos", "LVMH") == "Les Échos"

    def test_falls_back_to_org_name(self) -> None:
        assert _resolve_bw_display_name(None, "LVMH") == "LVMH"

    def test_falls_back_to_inconnue(self) -> None:
        assert _resolve_bw_display_name(None, None) == "inconnue"

    def test_empty_active_bw_falls_back(self) -> None:
        assert _resolve_bw_display_name("", "LVMH") == "LVMH"

    def test_whitespace_only_falls_back(self) -> None:
        """A pure-whitespace BW name is no name at all — fall through."""
        assert _resolve_bw_display_name("   ", "LVMH") == "LVMH"

    def test_both_empty_yields_inconnue(self) -> None:
        assert _resolve_bw_display_name("", "") == "inconnue"


# ---------------------------------------------------------------------------
# _filter_unknown_experts
# ---------------------------------------------------------------------------


class TestFilterUnknownExperts:
    """Used by ``filter_known_experts`` to avoid re-creating a contact
    for an expert who already has one — duplicate notifications would
    spam them and break analytics."""

    def test_drops_known_preserves_order(self) -> None:
        users = [_FakeUser(id=i) for i in (5, 1, 3, 2)]
        out = _filter_unknown_experts(users, {1, 3})
        assert [u.id for u in out] == [5, 2]

    def test_empty_known_keeps_all(self) -> None:
        users = [_FakeUser(id=1), _FakeUser(id=2)]
        assert _filter_unknown_experts(users, set()) == users

    def test_all_known_yields_empty(self) -> None:
        users = [_FakeUser(id=1), _FakeUser(id=2)]
        assert _filter_unknown_experts(users, {1, 2}) == []


# ---------------------------------------------------------------------------
# _filter_eligible_colleagues
# ---------------------------------------------------------------------------


class TestFilterEligibleColleagues:
    """The « non-mais » colleague suggestion list must :

    - never include the original expert (would loop the avis back) ;
    - never include someone already contacted for this avis ;
    - never include inactive accounts (no notifications would arrive).
    """

    def test_all_three_filters_combine(self) -> None:
        me = _FakeUser(id=1)
        contacted = _FakeUser(id=2)
        inactive = _FakeUser(id=3, active=False)
        keep = _FakeUser(id=4)
        out = _filter_eligible_colleagues(
            [me, contacted, inactive, keep],
            expert_id=1,
            already_contacted_ids={2},
        )
        assert out == [keep]

    def test_each_filter_independently(self) -> None:
        """Self-only / contacted-only / inactive-only exclusions."""
        a, b = _FakeUser(id=1), _FakeUser(id=2)
        # Self excluded.
        assert _filter_eligible_colleagues(
            [a, b], expert_id=1, already_contacted_ids=set()
        ) == [b]
        # Already-contacted excluded.
        assert _filter_eligible_colleagues(
            [a, b], expert_id=99, already_contacted_ids={1}
        ) == [b]
        # Inactive excluded.
        inactive = _FakeUser(id=3, active=False)
        assert _filter_eligible_colleagues(
            [a, inactive], expert_id=99, already_contacted_ids=set()
        ) == [a]


# ---------------------------------------------------------------------------
# _is_contact_removable
# ---------------------------------------------------------------------------


class TestIsContactRemovable:
    """Bug #0061-c : retargeting only ever added contacts. The predicate
    must say YES iff the contact can be silently dropped — never on a
    contact that has engaged (RDV started) or was chained in by the
    « non-mais » colleague suggestion (data safety)."""

    @pytest.mark.parametrize(
        ("contact", "desired_ids", "expected"),
        [
            # Clean : expert dropped, no engagement → removable.
            (
                _FakeContact(expert_id=1, status=EN_ATTENTE, rdv_status=NO_RDV),
                {2, 3},
                True,
            ),
            # Still selected → kept.
            (
                _FakeContact(expert_id=1, status=EN_ATTENTE, rdv_status=NO_RDV),
                {1, 2},
                False,
            ),
            # RDV started → kept (data safety).
            (
                _FakeContact(expert_id=1, status=EN_ATTENTE, rdv_status=OTHER_STATUS),
                {2},
                False,
            ),
            # Already replied → kept.
            (
                _FakeContact(expert_id=1, status=OTHER_STATUS, rdv_status=NO_RDV),
                {2},
                False,
            ),
            # Suggested via « non-mais » → kept (audit trail).
            (
                _FakeContact(
                    expert_id=1,
                    status=EN_ATTENTE,
                    rdv_status=NO_RDV,
                    suggested_by_user_id=99,
                ),
                {2},
                False,
            ),
        ],
    )
    def test_removable_truth_table(
        self,
        contact: _FakeContact,
        desired_ids: set[int],
        expected: bool,
    ) -> None:
        assert (
            _is_contact_removable(
                contact,
                desired_ids=desired_ids,
                rdv_no_status=NO_RDV,
                en_attente_status=EN_ATTENTE,
            )
            is expected
        )


# ---------------------------------------------------------------------------
# Notification message strings — pin the wording
# ---------------------------------------------------------------------------


class TestNotificationMessages:
    """All in-app notification messages are user-visible. A wording
    change must be deliberate — pinning the strings makes accidents
    fail loudly in CI."""

    def test_avis_message(self) -> None:
        assert (
            _format_notify_avis_message("Le scoop")
            == "Un nouvel avis d'enquête est disponible: Le scoop"
        )

    def test_rdv_proposed_message(self) -> None:
        assert _format_notify_rdv_proposed_message("Le scoop") == (
            "Proposition de rendez-vous pour l'avis d'enquête : Le scoop"
        )

    def test_rdv_accepted_message(self) -> None:
        assert (
            _format_notify_rdv_accepted_message("Alice")
            == "Alice a accepté un créneau pour le RDV"
        )

    def test_rdv_refused_message(self) -> None:
        assert (
            _format_notify_rdv_refused_message("Bob") == "Bob a refusé les RDV proposés"
        )

    def test_suggested_message(self) -> None:
        assert _format_suggested_message("Carole", "Le scoop") == (
            "Un avis d'enquête vous a été transmis par Carole : Le scoop"
        )


# ---------------------------------------------------------------------------
# _validate_notify_lengths
# ---------------------------------------------------------------------------


class TestValidateNotifyLengths:
    """The two parallel lists (experts, URLs) feed a strict-zip in
    ``notify_experts``. A length mismatch must raise with a useful
    message so the caller doesn't get a cryptic ValueError from zip."""

    def test_matching_lengths_returns_none(self) -> None:
        assert (
            _validate_notify_lengths([_FakeUser(id=1), _FakeUser(id=2)], ["u1", "u2"])
            is None
        )

    def test_both_empty_is_valid(self) -> None:
        assert _validate_notify_lengths([], []) is None

    def test_mismatch_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="must match in length"):
            _validate_notify_lengths([_FakeUser(id=1)], ["u1", "u2"])

    def test_error_message_quotes_counts(self) -> None:
        """The exact counts in the error message help the caller
        spot a missing URL in their builder loop."""
        with pytest.raises(ValueError) as exc_info:
            _validate_notify_lengths(
                [_FakeUser(id=1), _FakeUser(id=2), _FakeUser(id=3)],
                ["u1"],
            )
        msg = str(exc_info.value)
        assert "3 experts" in msg
        assert "1 urls" in msg
