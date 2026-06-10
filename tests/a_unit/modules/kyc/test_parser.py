# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Smoke tests for the KYC XLS model parser.

``XLSParser.parse()`` is expensive (~ 270 ms per call : openpyxl
iter_rows + four sequential passes over ~ 1k cells), so we parse the
model ONCE per test module via a module-scope fixture and share the
result across every assertion. This cuts the test-run cost roughly
3x without losing coverage.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.modules.kyc import kyc_models, xls_parser
from app.modules.kyc.survey_dataclass import SurveyProfile
from app.modules.kyc.survey_model import MODEL_FILENAME


@pytest.fixture(scope="module")
def model_source() -> Path:
    return Path(kyc_models.__file__).parent / MODEL_FILENAME


@pytest.fixture(scope="module")
def parsed(model_source: Path) -> xls_parser.XLSParser:
    """Parse the bundled KYC model exactly once per test module."""
    parser = xls_parser.XLSParser()
    parser.parse(model_source)
    return parser


def test_model_exists(model_source: Path) -> None:
    assert model_source.is_file()


def test_parse_accepts_path(parsed: xls_parser.XLSParser) -> None:
    """The module-scope fixture parses from a ``Path`` ; that the
    fixture build succeeds at all is the proof. We also assert on the
    parsed model shape so the test communicates intent."""
    assert isinstance(parsed.model, dict)


def test_parse_accepts_str(model_source: Path) -> None:
    """``XLSParser.parse`` also accepts ``str`` paths — pin the type
    union. This is the one place we deliberately re-parse, since the
    input-type check IS the test target."""
    parser = xls_parser.XLSParser()
    parser.parse(str(model_source))
    assert isinstance(parser.model, dict)


def test_parse_content(parsed: xls_parser.XLSParser) -> None:
    """Cross-check that profile P003 is present and well-typed."""
    result = parsed.model
    profiles = [p for p in result["profiles"] if p.id == "P003"]
    assert profiles
    profile3 = profiles[0]
    assert isinstance(profile3, SurveyProfile)
    assert profile3.id == "P003"
