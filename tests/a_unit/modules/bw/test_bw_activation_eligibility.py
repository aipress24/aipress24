# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket 0273 : tous les profils ne peuvent pas ouvrir un Business Wall.

Erwann Le Fur, étudiant en journalisme, arrivait sur l'initialisation
d'un « Business Wall for Journalist ». L'abonnement appartient à
l'établissement, pas à ses étudiants : `PROFILE_CODE_TO_BW2_TYPE`
envoyait `AC_ST` vers MICRO alors que son propre commentaire disait
« except students ».

Le périmètre retenu (arbitrage du 2026-08-01) couvre les étudiants,
les étudiants entrepreneurs et les doctorants.
"""

from __future__ import annotations

import pytest

from app.enums import ProfileEnum
from app.modules.bw.bw_activation.user_utils import (
    BW_INELIGIBLE_PROFILES,
    can_activate_business_wall,
    profile_code_of,
)


class _Profile:
    """Stand-in for the KYC profile: only `.profile_code` is read."""

    def __init__(self, profile_code: str) -> None:
        self.profile_code = profile_code


class _User:
    """Stand-in for `User`: only `.profile` is read."""

    def __init__(self, profile: _Profile | None) -> None:
        self.profile = profile


def _user_with_profile_code(code: str | None) -> _User:
    return _User(None if code is None else _Profile(code))


class TestIneligibleProfiles:
    @pytest.mark.parametrize(
        "profile_code",
        [ProfileEnum.AC_ST, ProfileEnum.AC_ST_ENT, ProfileEnum.AC_DOC],
    )
    def test_student_profiles_cannot_activate(self, profile_code: ProfileEnum):
        user = _user_with_profile_code(profile_code.name)

        assert can_activate_business_wall(user) is False

    def test_the_ineligible_set_is_exactly_the_agreed_one(self):
        """Widening this set silently would cut legitimate users off from
        their subscription — pin the agreed perimeter."""
        assert {
            ProfileEnum.AC_ST,
            ProfileEnum.AC_ST_ENT,
            ProfileEnum.AC_DOC,
        } == BW_INELIGIBLE_PROFILES


class TestEligibleProfiles:
    @pytest.mark.parametrize(
        "profile_code",
        [
            ProfileEnum.AC_DIR,  # directeur d'établissement : c'est lui qui souscrit
            ProfileEnum.AC_ENS,  # enseignant
            ProfileEnum.PM_JR_ME,  # journaliste en micro-entreprise
            ProfileEnum.PR_DIR,  # agence de RP
        ],
    )
    def test_professional_profiles_can_activate(self, profile_code: ProfileEnum):
        user = _user_with_profile_code(profile_code.name)

        assert can_activate_business_wall(user) is True

    def test_missing_profile_is_allowed(self):
        """A user who never completed the KYC has no profile code. The
        funnel already copes with that (`guess_best_bw_type` defaults to
        MEDIA); refusing them would lock out legitimate accounts to catch
        a claim the profile doesn't actually make."""
        assert can_activate_business_wall(_user_with_profile_code(None)) is True

    def test_unknown_profile_code_is_allowed(self):
        """Same reasoning for a legacy / imported code outside ProfileEnum."""
        assert can_activate_business_wall(_user_with_profile_code("BOGUS")) is True


class TestProfileCodeOf:
    def test_returns_the_enum_member(self):
        user = _user_with_profile_code(ProfileEnum.AC_ST.name)

        assert profile_code_of(user) == ProfileEnum.AC_ST

    @pytest.mark.parametrize("code", [None, "BOGUS"])
    def test_returns_none_when_unusable(self, code: str | None):
        assert profile_code_of(_user_with_profile_code(code)) is None
