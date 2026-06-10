# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ``bw_contact_name_email``.

WHY: ``bw_contact_name_email(bw)`` is the single source of contact info
used by the BW dashboard to surface partner-BW owners (see
``get_pending_pr_bw_info_list`` and ``get_current_pr_bw_info_list``).
The production code reaches into ``db.session`` via :func:`get_obj` to
fetch the owner ``User`` row, which used to be tested only at the
integration level.

To honour the project rule "Don't use mocks. Prefer stubs.", we exposed
a keyword-only ``loader=`` default-arg seam (Pattern B) on the
production function. Tests pass a plain callable returning a stand-in
``User`` object that exposes ``full_name`` and ``email`` attributes —
no mocks, no patches, no fixture-level monkey patching. The
production default (``loader=None``) still routes through ``get_obj``,
so every existing call site keeps working without changes.

We assert tangible state: the returned ``(name, email)`` tuple is what
came out of the loader's ``User``, the ``owner_id`` passed into the
loader is the BW's owner id, and exotic-but-valid attribute values
(empty string, whitespace, Unicode) round-trip unchanged.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any

import pytest

from app.modules.bw.bw_activation.utils import bw_contact_name_email


@dataclass
class FakeUser:
    """Stand-in for ``app.models.auth.User``.

    Only the two attributes consumed by ``bw_contact_name_email``
    (``full_name`` and ``email``) are needed.
    """

    full_name: str
    email: str


@dataclass
class FakeBW:
    """Stand-in for ``BusinessWall``.

    Only ``owner_id`` is consumed by ``bw_contact_name_email``.
    """

    owner_id: int


def make_loader(user: FakeUser, *, expected_id: int | None = None):
    """Return a tiny pure-function ``loader`` for DI.

    If ``expected_id`` is given, the loader asserts the BW owner id is
    forwarded faithfully — turning a behavioural concern (which id was
    looked up) into a *state* check at call time. The loader still
    returns ``user``, so the test body keeps asserting on returned
    state (the tuple), not on any recorder list.
    """

    def loader(owner_id: int) -> FakeUser:
        if expected_id is not None:
            assert owner_id == expected_id, (
                f"loader received owner_id={owner_id!r}, "
                f"expected {expected_id!r}"
            )
        return user

    return loader


class TestBwContactNameEmail:
    """Basic happy-path behaviour of ``bw_contact_name_email``."""

    def test_returns_full_name_and_email_tuple(self) -> None:
        user = FakeUser(full_name="Alice Martin", email="alice@example.org")
        bw = FakeBW(owner_id=42)

        result = bw_contact_name_email(bw, loader=make_loader(user))

        assert result == ("Alice Martin", "alice@example.org")

    def test_result_is_a_tuple_of_two_strings(self) -> None:
        user = FakeUser(full_name="Bob", email="bob@example.org")
        bw = FakeBW(owner_id=1)

        result = bw_contact_name_email(bw, loader=make_loader(user))

        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(item, str) for item in result)

    def test_name_is_first_email_is_second(self) -> None:
        """The order must stay (name, email) — downstream code indexes
        positionally (see ``get_pending_pr_bw_info_list``)."""
        user = FakeUser(full_name="THE-NAME", email="THE-EMAIL@x")
        bw = FakeBW(owner_id=7)

        name, email = bw_contact_name_email(bw, loader=make_loader(user))

        assert name == "THE-NAME"
        assert email == "THE-EMAIL@x"


class TestOwnerIdForwarding:
    """The BW's ``owner_id`` must be the id passed to the loader."""

    @pytest.mark.parametrize("owner_id", [1, 42, 999_999, 2**31 - 1])
    def test_owner_id_is_forwarded_to_loader(self, owner_id: int) -> None:
        user = FakeUser(full_name="X", email="x@y")
        bw = FakeBW(owner_id=owner_id)

        result = bw_contact_name_email(
            bw, loader=make_loader(user, expected_id=owner_id)
        )

        # If the in-loader assertion fired, we'd never reach this line.
        assert result == ("X", "x@y")

    def test_two_different_bws_route_to_their_own_owner(self) -> None:
        """A loader that branches on owner_id yields per-BW results — no
        cross-contamination between calls."""
        registry = {
            10: FakeUser(full_name="Owner Ten", email="ten@x"),
            20: FakeUser(full_name="Owner Twenty", email="twenty@x"),
        }

        def loader(owner_id: int) -> FakeUser:
            return registry[owner_id]

        bw_a = FakeBW(owner_id=10)
        bw_b = FakeBW(owner_id=20)

        result_a = bw_contact_name_email(bw_a, loader=loader)
        result_b = bw_contact_name_email(bw_b, loader=loader)

        assert result_a == ("Owner Ten", "ten@x")
        assert result_b == ("Owner Twenty", "twenty@x")


class TestUserAttributeVariants:
    """The function must passthrough whatever the user object exposes."""

    @pytest.mark.parametrize(
        ("full_name", "email"),
        [
            ("Alice Martin", "alice@example.org"),
            # Unicode / accents — common in FR newsroom data
            ("Élise Léon-Müller", "elise@écho.fr"),
            # Empty string is a legitimate state (missing optional field)
            ("", ""),
            # Whitespace must NOT be silently stripped — callers may rely
            # on it to detect "looks blank" themselves.
            ("   ", "  "),
            # Very long string (DB columns are wide; no clipping here)
            ("X" * 500, "y" * 200 + "@example.org"),
            # Mixed-case email — no normalization
            ("Bob", "BoB@Example.ORG"),
            # Plus-tag email
            ("Carol", "carol+bw@example.org"),
        ],
    )
    def test_passthrough_of_full_name_and_email(
        self, full_name: str, email: str
    ) -> None:
        user = FakeUser(full_name=full_name, email=email)
        bw = FakeBW(owner_id=1)

        result = bw_contact_name_email(bw, loader=make_loader(user))

        assert result == (full_name, email)


class TestLoaderContract:
    """The ``loader`` keyword is the documented DI seam."""

    def test_loader_is_keyword_only(self) -> None:
        """Pattern B requires the seam to be keyword-only so a caller
        can't accidentally pass a User positionally where a BW is
        expected."""
        user = FakeUser(full_name="K", email="k@x")
        bw = FakeBW(owner_id=3)

        # Re-bind via ``Any`` so the static checker doesn't flag the
        # intentionally-wrong positional call we're about to make.
        call: Any = bw_contact_name_email
        with pytest.raises(TypeError):
            # Positional second arg should fail — loader is kw-only.
            call(bw, make_loader(user))

    def test_loader_default_is_none_so_existing_callers_keep_working(
        self,
    ) -> None:
        """Backward-compat guard. The seam must default to ``None`` so
        the production path (db.session via ``get_obj``) is unchanged
        for callers that don't know about ``loader=``."""
        sig = inspect.signature(bw_contact_name_email)
        loader_param = sig.parameters["loader"]
        assert loader_param.default is None
        assert loader_param.kind is inspect.Parameter.KEYWORD_ONLY

    def test_loader_callable_is_invoked_exactly_via_returned_state(
        self,
    ) -> None:
        """We don't count invocations (forbidden recorder pattern); we
        prove the loader was used by observing that *its* return value
        flowed back out of ``bw_contact_name_email``."""
        sentinel = FakeUser(
            full_name="sentinel-full-name", email="sentinel@e"
        )
        bw = FakeBW(owner_id=99)

        result = bw_contact_name_email(bw, loader=lambda _id: sentinel)

        # Only the loader's user could have produced these strings.
        assert result == ("sentinel-full-name", "sentinel@e")


class TestLoaderErrors:
    """Errors from the loader should propagate unchanged."""

    def test_loader_exception_propagates(self) -> None:
        bw = FakeBW(owner_id=1)

        def boom(_owner_id: int) -> FakeUser:
            msg = "db unavailable"
            raise RuntimeError(msg)

        with pytest.raises(RuntimeError, match="db unavailable"):
            bw_contact_name_email(bw, loader=boom)

    def test_loader_returning_object_without_full_name_raises(self) -> None:
        """A loader that returns something not duck-typing as a User
        should fail loudly at attribute access — better than silently
        returning ``None`` or an empty tuple."""

        class NoFullName:
            email = "x@y"

        bw = FakeBW(owner_id=1)

        with pytest.raises(AttributeError):
            bw_contact_name_email(bw, loader=lambda _id: NoFullName())

    def test_loader_returning_object_without_email_raises(self) -> None:
        class NoEmail:
            full_name = "Solo"

        bw = FakeBW(owner_id=1)

        with pytest.raises(AttributeError):
            bw_contact_name_email(bw, loader=lambda _id: NoEmail())
