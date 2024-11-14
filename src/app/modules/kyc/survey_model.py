# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import cache
from importlib import resources as rso
from typing import Any

from . import kyc_models
from .survey_dataclass import SurveyField, SurveyProfile
from .xls_parser import XLSParser

MODEL_FILENAME = "MVP-2-KYC-Commons-30.xlsx"


def load_survey_model() -> dict[str, Any]:
    """Content of the XLS survey.

    Format:
    {
        "communities": self.communities,
        "survey_fields": self.survey_fields,
        "profiles": self.profiles,
    }
    """
    parser = XLSParser()
    xls_file = rso.files(kyc_models) / MODEL_FILENAME
    parser.parse(xls_file)
    return parser.model


def get_survey_model() -> dict[str, Any]:
    return survey


@cache
def get_survey_profile(profile_id: str) -> SurveyProfile:
    for profile in survey["profiles"]:
        if profile.id == profile_id:
            return profile
    raise ValueError(f"Unknown profile: {profile_id}")


@cache
def get_survey_profile_ids() -> list[str]:
    return [p.id for p in survey["profiles"]]


@cache
def get_survey_fields() -> list[SurveyField]:
    return list(survey["survey_fields"].values())


survey = load_survey_model()
