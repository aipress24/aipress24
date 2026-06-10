# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the PR-Business-Wall partnership listing helpers in
`app.modules.bw.bw_activation.utils`.

These functions sit on the hot path of the *Press Relations* dashboard :
given a BusinessWall, they enumerate the partner agencies in each
lifecycle state (active / invited / rejected / expired) and shape them
into dicts that the Jinja templates consume. Three things must hold for
the dashboard to be correct :

1. The *status filter* must let exactly the right partnership statuses
   through. A leaky filter would surface revoked or expired agencies as
   « current partners » — a privacy / authorization bug, not just a
   cosmetic glitch.
2. The *partner-bw lookup* must use the BW id stored on the
   `Partnership` row (not the BW id of the BusinessWall on which the
   partnership lives). Confusing the two would show the owner their own
   BW as their partner.
3. The two info-list builders must produce a stable dict shape — keys
   are read directly by the templates, and the pending list translates
   raw status strings to French dashboard labels (`"invited"` →
   `"invitation en cours"`). Drift in either silently breaks the UI.

To keep these tests at the *unit* tier we exercise the helpers with
stand-in BusinessWall / Partnership objects and inject a stand-in
`BusinessWallService` via the new keyword-only `service=` argument
(Pattern B). The pure dict builders (`_pending_bw_to_info_dict`,
`_current_bw_to_info_dict`) take plain values, so they need no
injection (Pattern A — functional core). No database, no Flask app
context, no mocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.modules.bw.bw_activation.utils import (
    _current_bw_to_info_dict,
    _get_press_relation_bw_list_for_status,
    _pending_bw_to_info_dict,
    get_current_press_relation_bw_list,
    get_invited_press_relation_bw_list,
    get_pending_press_relation_bw_list,
)

# ---------------------------------------------------------------------------
# Stand-in collaborators (real fakes — Pattern C inside Pattern B).
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class StubBusinessWall:
    """Minimal BusinessWall stand-in.

    Only the attributes the helpers read are present : `id`, `name_safe`,
    and a list of `partnerships`. No SQLAlchemy state, no relationships
    loaded — assignments are plain Python.

    `eq=False` keeps default identity-based hashing so instances can be
    used inside `set` literals in the tests below (mutable
    `partnerships` would otherwise make the dataclass unhashable).
    """

    id: UUID = field(default_factory=uuid4)
    name_safe: str = "BW"
    partnerships: list[Any] = field(default_factory=list)


@dataclass
class StubPartnership:
    """Minimal Partnership stand-in matching the attributes the
    `_get_press_relation_bw_list_for_status` reads : `status` and
    `partner_bw_id`."""

    status: str
    partner_bw_id: str | None


class FakeBusinessWallService:
    """In-memory BusinessWallService stand-in.

    Implements only `.get(uuid) -> BusinessWall | None`, which is the
    one method the production helper calls. Looking up an unknown id
    returns `None` — same contract as the real
    `SQLAlchemySyncRepositoryService.get`.
    """

    def __init__(self, bws: list[StubBusinessWall]) -> None:
        self._by_id: dict[UUID, StubBusinessWall] = {bw.id: bw for bw in bws}

    def get(self, bw_id: UUID) -> StubBusinessWall | None:
        return self._by_id.get(bw_id)


def _make_partner(name: str = "Partner") -> StubBusinessWall:
    """Build a partner BW with a fresh UUID and the given display name."""
    return StubBusinessWall(name_safe=name)


# ---------------------------------------------------------------------------
# _get_press_relation_bw_list_for_status — the core filter + lookup.
# ---------------------------------------------------------------------------


class TestGetPressRelationBwListForStatus:
    """The private helper is the single source of truth for « which
    partner BW is in which state ». All three public wrappers funnel
    through it, so pinning its behaviour pins theirs."""

    def test_no_partnerships_returns_empty_list(self) -> None:
        bw = StubBusinessWall(partnerships=[])
        service = FakeBusinessWallService([])

        result = _get_press_relation_bw_list_for_status(
            bw, {"active"}, service=service
        )

        assert result == []

    def test_partnerships_is_none_treated_as_empty(self) -> None:
        # The helper guards `businesswall.partnerships or []` — a
        # never-loaded relationship must not crash the dashboard.
        bw = StubBusinessWall()
        bw.partnerships = None  # type: ignore[assignment]
        service = FakeBusinessWallService([])

        result = _get_press_relation_bw_list_for_status(
            bw, {"active"}, service=service
        )

        assert result == []

    def test_returns_only_matching_status(self) -> None:
        active_partner = _make_partner("Active")
        revoked_partner = _make_partner("Revoked")
        bw = StubBusinessWall(
            partnerships=[
                StubPartnership("active", str(active_partner.id)),
                StubPartnership("revoked", str(revoked_partner.id)),
            ]
        )
        service = FakeBusinessWallService([active_partner, revoked_partner])

        result = _get_press_relation_bw_list_for_status(
            bw, {"active"}, service=service
        )

        assert result == [(active_partner, "active")]

    def test_returns_multi_status_set(self) -> None:
        invited = _make_partner("Inv")
        rejected = _make_partner("Rej")
        active = _make_partner("Act")
        bw = StubBusinessWall(
            partnerships=[
                StubPartnership("invited", str(invited.id)),
                StubPartnership("rejected", str(rejected.id)),
                StubPartnership("active", str(active.id)),
            ]
        )
        service = FakeBusinessWallService([invited, rejected, active])

        result = _get_press_relation_bw_list_for_status(
            bw, {"invited", "rejected"}, service=service
        )

        # Order preserved — important for stable dashboard rendering.
        assert [s for _, s in result] == ["invited", "rejected"]
        assert {bw_ for bw_, _ in result} == {invited, rejected}

    def test_skips_partnership_with_missing_partner_bw_id(self) -> None:
        # Empty string and None are both falsy — both must be dropped to
        # avoid passing `UUID("")` into the service lookup.
        partner = _make_partner("Real")
        bw = StubBusinessWall(
            partnerships=[
                StubPartnership("active", None),
                StubPartnership("active", ""),
                StubPartnership("active", str(partner.id)),
            ]
        )
        service = FakeBusinessWallService([partner])

        result = _get_press_relation_bw_list_for_status(
            bw, {"active"}, service=service
        )

        assert result == [(partner, "active")]

    def test_skips_partnership_when_service_returns_none(self) -> None:
        # A partnership row pointing at a deleted partner BW must not
        # surface as a dashboard entry — the helper drops it silently.
        ghost_id = str(uuid4())
        bw = StubBusinessWall(
            partnerships=[StubPartnership("active", ghost_id)]
        )
        service = FakeBusinessWallService([])  # ghost is unknown

        result = _get_press_relation_bw_list_for_status(
            bw, {"active"}, service=service
        )

        assert result == []

    def test_resolves_partner_via_uuid_not_string(self) -> None:
        # Pin the contract that `partner_bw_id` is stringified at storage
        # and parsed back to `UUID` for the service lookup. A stub that
        # only accepts UUID keys (not strings) proves this.
        partner = _make_partner("UUIDPartner")
        bw = StubBusinessWall(
            partnerships=[StubPartnership("active", str(partner.id))]
        )
        service = FakeBusinessWallService([partner])

        result = _get_press_relation_bw_list_for_status(
            bw, {"active"}, service=service
        )

        assert result == [(partner, "active")]


# ---------------------------------------------------------------------------
# Three thin wrappers — pin the status set they request.
# ---------------------------------------------------------------------------


class TestPublicWrappers:
    """Each wrapper is a one-liner that picks a status set. The tests
    pin that set : if someone widens or narrows the filter, dashboards
    leak or hide rows, both of which the partnership product owner has
    explicitly forbidden."""

    @pytest.fixture
    def mixed_bw(self) -> tuple[StubBusinessWall, FakeBusinessWallService, dict[str, StubBusinessWall]]:
        """A BusinessWall with one partner in every Partnership state."""
        partners = {
            "invited": _make_partner("Invited Co"),
            "accepted": _make_partner("Accepted Co"),
            "active": _make_partner("Active Co"),
            "rejected": _make_partner("Rejected Co"),
            "revoked": _make_partner("Revoked Co"),
            "expired": _make_partner("Expired Co"),
        }
        bw = StubBusinessWall(
            partnerships=[
                StubPartnership(status, str(partner.id))
                for status, partner in partners.items()
            ]
        )
        service = FakeBusinessWallService(list(partners.values()))
        return bw, service, partners

    def test_get_current_keeps_only_active(
        self,
        mixed_bw: tuple[
            StubBusinessWall, FakeBusinessWallService, dict[str, StubBusinessWall]
        ],
    ) -> None:
        bw, service, partners = mixed_bw

        result = get_current_press_relation_bw_list(bw, service=service)

        assert result == [partners["active"]]

    def test_get_invited_keeps_only_invited(
        self,
        mixed_bw: tuple[
            StubBusinessWall, FakeBusinessWallService, dict[str, StubBusinessWall]
        ],
    ) -> None:
        bw, service, partners = mixed_bw

        result = get_invited_press_relation_bw_list(bw, service=service)

        assert result == [partners["invited"]]

    def test_get_pending_keeps_invited_rejected_expired(
        self,
        mixed_bw: tuple[
            StubBusinessWall, FakeBusinessWallService, dict[str, StubBusinessWall]
        ],
    ) -> None:
        bw, service, partners = mixed_bw

        result = get_pending_press_relation_bw_list(bw, service=service)

        # The "pending" bucket explicitly includes rejected + expired —
        # the dashboard surfaces them under « invitations à relancer ».
        statuses = sorted(s for _, s in result)
        assert statuses == ["expired", "invited", "rejected"]
        assert {bw_ for bw_, _ in result} == {
            partners["invited"],
            partners["rejected"],
            partners["expired"],
        }

    def test_get_pending_excludes_accepted_active_revoked(
        self,
        mixed_bw: tuple[
            StubBusinessWall, FakeBusinessWallService, dict[str, StubBusinessWall]
        ],
    ) -> None:
        # Negative-form pin : accepted / active / revoked must NOT show
        # up under « pending ». The original implementation defined the
        # filter set inline — easy to typo a value back in.
        bw, service, _ = mixed_bw

        result = get_pending_press_relation_bw_list(bw, service=service)

        statuses = {s for _, s in result}
        assert "accepted" not in statuses
        assert "active" not in statuses
        assert "revoked" not in statuses


# ---------------------------------------------------------------------------
# Pure dict builders — Pattern A (functional core).
# ---------------------------------------------------------------------------


class TestPendingInfoDictBuilder:
    """The pending-PR-BW dashboard reads four keys from each row. The
    `bw_status` value is a French translation of the raw partnership
    status. Both contracts pinned here."""

    @pytest.mark.parametrize(
        ("raw_status", "expected_label"),
        [
            ("invited", "invitation en cours"),
            ("rejected", "invitation rejetée"),
            ("expired", "invitation expirée"),
        ],
    )
    def test_translates_known_status(
        self, raw_status: str, expected_label: str
    ) -> None:
        bw = _make_partner("Acme PR")

        info = _pending_bw_to_info_dict(bw, raw_status, ("Alice", "a@x"))

        assert info["bw_status"] == expected_label

    def test_dict_shape_for_pending_entry(self) -> None:
        bw = _make_partner("Acme PR")

        info = _pending_bw_to_info_dict(bw, "invited", ("Alice", "a@x"))

        assert set(info) == {
            "bw_name",
            "bw_contact_name",
            "bw_contact_email",
            "bw_status",
        }
        assert info["bw_name"] == "Acme PR"
        assert info["bw_contact_name"] == "Alice"
        assert info["bw_contact_email"] == "a@x"

    def test_unknown_status_falls_back_to_raw_value(self) -> None:
        # Defence in depth : if a brand-new Partnership status reaches
        # the dashboard before its label is added, surface the raw value
        # instead of KeyError-ing the whole page.
        bw = _make_partner("Acme")

        info = _pending_bw_to_info_dict(bw, "mystery", ("A", "a@x"))

        assert info["bw_status"] == "mystery"


class TestCurrentInfoDictBuilder:
    """The active-PR-BW dashboard reads four keys from each row,
    including the stringified BW id used as an `<a href>` target."""

    def test_dict_shape_for_current_entry(self) -> None:
        partner_id = UUID("00000000-0000-0000-0000-000000000001")
        bw = StubBusinessWall(id=partner_id, name_safe="Acme PR")

        info = _current_bw_to_info_dict(bw, ("Bob", "b@x"))

        assert info == {
            "bw_name": "Acme PR",
            "bw_contact_name": "Bob",
            "bw_contact_email": "b@x",
            "bw_id": "00000000-0000-0000-0000-000000000001",
        }

    def test_bw_id_is_always_stringified(self) -> None:
        # Pin : `bw_id` is a STRING in the dict — Jinja `{{ row.bw_id }}`
        # used in href values must not get a UUID object that renders
        # with hyphens already, but the explicit `str()` makes the
        # contract obvious and survives a future `id` type change.
        bw = StubBusinessWall(id=uuid4())

        info = _current_bw_to_info_dict(bw, ("c", "c@x"))

        assert isinstance(info["bw_id"], str)
