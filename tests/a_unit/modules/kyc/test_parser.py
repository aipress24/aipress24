# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.kyc import kyc_models, xls_parser
from app.modules.kyc.survey_dataclass import SurveyProfile
from app.modules.kyc.survey_model import MODEL_FILENAME


@pytest.fixture
def model_source() -> Path:
    return Path(kyc_models.__file__).parent / MODEL_FILENAME
    # return Path(__file__).parent.parent / "kyc_models" / MODEL_FILENAME


def test_model_exists(model_source) -> None:
    assert model_source.is_file()


def test_parse_str(model_source) -> None:
    model_loader = xls_parser.XLSParser()
    model_loader.parse(str(model_source))
    assert isinstance(model_loader.model, dict)


def test_parse_path(model_source) -> None:
    model_loader = xls_parser.XLSParser()
    model_loader.parse(model_source)
    assert isinstance(model_loader.model, dict)


def test_parse_content(model_source) -> None:
    model_loader = xls_parser.XLSParser()
    model_loader.parse(model_source)
    result = model_loader.model
    profiles = [p for p in result["profiles"] if p.id == "P003"]
    assert profiles
    profile3 = profiles[0]
    assert isinstance(profile3, SurveyProfile)
    assert profile3.id == "P003"
