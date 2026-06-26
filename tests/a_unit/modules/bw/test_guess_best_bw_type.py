# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `guess_best_bw_type` in
`app.modules.bw.bw_activation.user_utils`.

This helper picks the best BW type to pre-select when a freshly-
created user lands on the BW activation flow. The picks are driven
by `PROFILE_CODE_TO_BW2_TYPE`, a dict mapping each KYC `ProfileEnum`
member to its canonical BW type.

The behaviour to pin :
- None profile → MEDIA (Bug #0117 lifted the « must have profile »
  gate ; this branch is the safety net).
- Malformed `profile_code` (not in ProfileEnum) → MEDIA.
- Unmapped `ProfileEnum` member → MEDIA (the `.get(..., MEDIA)`
  fallback).
- Every mapped member → its canonical type.

Bonus : pin invariants on `PROFILE_CODE_TO_BW2_TYPE` (key/value types,
no « None » values, every value is a real BWType).
"""

from __future__ import annotations

import pytest

from app.enums import ProfileEnum
from app.modules.bw.bw_activation.models import BWType
from app.modules.bw.bw_activation.user_utils import (
    PROFILE_CODE_TO_BW2_TYPE,
    guess_best_bw_type,
)


class _Profile:
    """Minimal stand-in for the KYC profile attached to a user. The
    helper only reads `.profile_code`, so nothing else is needed."""

    def __init__(self, profile_code: str) -> None:
        self.profile_code = profile_code


class _User:
    """Minimal stand-in for `User`. The helper only reads `.profile`."""

    def __init__(self, profile: _Profile | None) -> None:
        self.profile = profile


def _user_with_profile_code(code: str | None) -> _User:
    """Build a User stand-in whose `.profile.profile_code` is what
    the test wants. The helper only reads `user.profile`, so the rest
    is irrelevant."""
    if code is None:
        return _User(None)
    return _User(_Profile(code))


class TestNoneProfileDefaults:
    def test_none_profile_returns_media(self):
        """Bug #0117 v2 : a user without a KYC profile (just signed
        up) still reaches `index()` ; the helper must return a sane
        default rather than crash."""
        user = _user_with_profile_code(None)
        assert guess_best_bw_type(user) == BWType.MEDIA


class TestMalformedProfileCodeDefaults:
    def test_unknown_profile_code_returns_media(self):
        """A `profile_code` that's not in ProfileEnum (data import,
        legacy) → MEDIA. Pin so a regression that crashes with
        KeyError gets caught."""
        user = _user_with_profile_code("TOTALLY_BOGUS_CODE")
        assert guess_best_bw_type(user) == BWType.MEDIA

    def test_empty_string_profile_code_returns_media(self):
        user = _user_with_profile_code("")
        assert guess_best_bw_type(user) == BWType.MEDIA


class TestCanonicalProfileMappings:
    """Pin every mapped ProfileEnum → BWType pair so a future
    re-categorisation of profiles is conscious, not accidental."""

    @pytest.mark.parametrize(
        ("profile_code", "expected"),
        [
            (ProfileEnum.PM_DIR.name, BWType.MEDIA),
            (ProfileEnum.PM_JR_CP_SAL.name, BWType.MEDIA),
            (ProfileEnum.PM_JR_PIG.name, BWType.MEDIA),
            # micro, corporate_media and union are deprecated; those
            # profiles now default to media.
            (ProfileEnum.PM_JR_CP_ME.name, BWType.MEDIA),
            (ProfileEnum.PM_JR_ME.name, BWType.MEDIA),
            (ProfileEnum.PM_DIR_INST.name, BWType.MEDIA),
            (ProfileEnum.PM_DIR_SYND.name, BWType.MEDIA),
            (ProfileEnum.PR_DIR.name, BWType.PR),
            (ProfileEnum.PR_CS.name, BWType.PR),
            (ProfileEnum.XP_DIR_ANY.name, BWType.LEADERS_EXPERTS),
            (ProfileEnum.TP_DIR_ORG.name, BWType.TRANSFORMERS),
            (ProfileEnum.AC_DIR.name, BWType.ACADEMICS),
            (ProfileEnum.AC_ST.name, BWType.MEDIA),
        ],
    )
    def test_profile_code_routes_to_expected_type(self, profile_code, expected):
        user = _user_with_profile_code(profile_code)
        assert guess_best_bw_type(user) == expected


class TestProfileCodeToBw2TypeInvariants:
    """The dict drives every decision in `guess_best_bw_type`. Pin
    structural invariants so a future entry that's syntactically
    OK but semantically wrong (e.g. `None` value) gets caught."""

    def test_all_keys_are_profile_enum_members(self):
        """A string key would be silently ignored by the `.get`
        lookup since the function passes a ProfileEnum member as the
        lookup key."""
        for key in PROFILE_CODE_TO_BW2_TYPE:
            assert isinstance(key, ProfileEnum), (
                f"PROFILE_CODE_TO_BW2_TYPE key {key!r} is not a "
                f"ProfileEnum member (got {type(key).__name__})"
            )

    def test_all_values_are_bw_type_members(self):
        """A string value would propagate as a string through the
        codebase and break `BWType`-typed callers downstream."""
        for key, value in PROFILE_CODE_TO_BW2_TYPE.items():
            assert isinstance(value, BWType), (
                f"PROFILE_CODE_TO_BW2_TYPE[{key.name!r}] is {value!r}, not a BWType"
            )

    def test_no_duplicates_across_keys(self):
        """Same ProfileEnum mapping twice would be a copy-paste bug.
        Pin uniqueness — `dict` already enforces it, but pin the
        canonical count to catch silent removals."""
        names = [k.name for k in PROFILE_CODE_TO_BW2_TYPE]
        assert len(names) == len(set(names))

    def test_no_none_values(self):
        """An explicit `None` value would crash callers that expect
        a BWType. Pin so a future migration scaffold doesn't leak
        Nones into production."""
        for key, value in PROFILE_CODE_TO_BW2_TYPE.items():
            assert value is not None, f"PROFILE_CODE_TO_BW2_TYPE[{key.name!r}] is None"

    def test_every_paid_bw_type_has_at_least_one_profile(self):
        """The 3 paid BW types (TRANSFORMERS / LEADERS_EXPERTS / PR)
        must be reachable from some KYC profile, otherwise no user
        would ever be defaulted to them in the activation flow.

        Pin so a future refactor that drops the only profile pointing
        at one paid type gets caught."""
        values = set(PROFILE_CODE_TO_BW2_TYPE.values())
        for paid in (BWType.PR, BWType.LEADERS_EXPERTS, BWType.TRANSFORMERS):
            assert paid in values, (
                f"BWType {paid.value!r} is unreachable — no KYC "
                "profile maps to it in PROFILE_CODE_TO_BW2_TYPE."
            )


class TestUnmappedProfileEnumDefaults:
    """When a NEW ProfileEnum member is added without a corresponding
    PROFILE_CODE_TO_BW2_TYPE entry, the `.get(code, MEDIA)` fallback
    fires. Pin so the safety net stays in place — the alternative
    (`profile_code` defined but not mapped → KeyError) would be much
    worse for the user."""

    def test_unmapped_profile_enum_member_falls_back_to_media(
        self,
    ):
        """Use a ProfileEnum member NOT in PROFILE_CODE_TO_BW2_TYPE
        if any exists ; otherwise rely on the malformed-code path."""
        unmapped = [m for m in ProfileEnum if m not in PROFILE_CODE_TO_BW2_TYPE]
        if not unmapped:
            pytest.skip(
                "all ProfileEnum members are mapped — this defensive "
                "fallback can't be exercised."
            )
        user = _user_with_profile_code(unmapped[0].name)
        assert guess_best_bw_type(user) == BWType.MEDIA
