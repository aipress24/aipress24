# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ui/labels.py"""

from __future__ import annotations

from app.enums import OrganisationTypeEnum, ProfileEnum
from app.ui.labels import LABELS_PROFILE, make_label


def test_make_label_for_all_profiles() -> None:
    """Test make_label works for all ProfileEnum values."""
    for profile in ProfileEnum:
        result = make_label(profile)
        assert result == LABELS_PROFILE[profile]
        assert isinstance(result, str)


def test_make_label_for_organisation_types() -> None:
    """Test make_label for OrganisationTypeEnum."""
    assert make_label(OrganisationTypeEnum.MEDIA) == "Média"
    assert make_label(OrganisationTypeEnum.AUTO) == "Non officialisée"
    assert make_label(OrganisationTypeEnum.COM) == "PR agency"
