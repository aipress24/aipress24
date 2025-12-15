# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/geonames module."""

from __future__ import annotations

import pytest

from app.services.geonames._service import get_dept_name, is_dept_in_region


# Valid department/region pairs for metropolitan France
VALID_DEPT_REGION_PAIRS = [
    ("Paris", "Île-de-France"),
    ("Ain", "Auvergne-Rhône-Alpes"),
    ("Aisne", "Hauts-de-France"),
    ("Allier", "Auvergne-Rhône-Alpes"),
    ("Alpes-de-Haute-Provence", "Provence-Alpes-Côte d'Azur"),
    ("Hautes-Alpes", "Provence-Alpes-Côte d'Azur"),
    ("Alpes-Maritimes", "Provence-Alpes-Côte d'Azur"),
    ("Ardèche", "Auvergne-Rhône-Alpes"),
    ("Ardennes", "Grand Est"),
    ("Ariège", "Occitanie"),
    ("Aube", "Grand Est"),
    ("Aude", "Occitanie"),
    ("Aveyron", "Occitanie"),
    ("Bouches-du-Rhône", "Provence-Alpes-Côte d'Azur"),
    ("Calvados", "Normandie"),
]

# Invalid department/region pairs (mismatched)
INVALID_DEPT_REGION_PAIRS = [
    ("Calvados", "Île-de-France"),
    ("Ain", "Normandie"),
    ("Aisne", "Auvergne-Rhône-Alpes"),
    ("Allier", "Hauts-de-France"),
    ("Alpes-de-Haute-Provence", "Auvergne-Rhône-Alpes"),
]

# Overseas departments and their regions
OVERSEAS_DEPT_REGION_PAIRS = [
    ("Guadeloupe", "Guadeloupe"),
    ("Martinique", "Martinique"),
    ("Guyane", "Guyane"),
    ("La Réunion", "La Réunion"),
    ("Mayotte", "Mayotte"),
]

# Corsica departments
CORSICA_DEPT_REGION_PAIRS = [
    ("South Corsica", "Corse"),
    ("Upper Corsica", "Corse"),
]

# Standard department codes and names
STANDARD_DEPT_CODES = [
    ("01", "Ain"),
    ("75", "Paris"),
    ("13", "Bouches-du-Rhône"),
    ("59", "Nord"),
    ("33", "Gironde"),
]

# Overseas territory codes
OVERSEAS_DEPT_CODES = [
    ("971", "Guadeloupe"),
    ("972", "Martinique"),
    ("973", "Guyane"),
    ("974", "La Réunion"),
    ("976", "Mayotte"),
]

# Special territory codes
SPECIAL_TERRITORY_CODES = [
    ("977", "Saint-Barthélemy"),
    ("978", "Saint-Martin"),
    ("988", "Nouvelle-Calédonie"),
    ("989", "Île de Clipperton"),
]


class TestIsDeptInRegion:
    """Test suite for is_dept_in_region function."""

    @pytest.mark.parametrize("dept,region", VALID_DEPT_REGION_PAIRS)
    def test_valid_metropolitan_pairs(self, dept: str, region: str) -> None:
        """Test valid department/region pairs for metropolitan France."""
        assert is_dept_in_region(dept, region) is True

    @pytest.mark.parametrize("dept,region", INVALID_DEPT_REGION_PAIRS)
    def test_invalid_metropolitan_pairs(self, dept: str, region: str) -> None:
        """Test mismatched department/region pairs return False."""
        assert is_dept_in_region(dept, region) is False

    @pytest.mark.parametrize("dept,region", OVERSEAS_DEPT_REGION_PAIRS)
    def test_overseas_departments(self, dept: str, region: str) -> None:
        """Test overseas departments match their regions."""
        assert is_dept_in_region(dept, region) is True

    @pytest.mark.parametrize(
        "dept,wrong_region",
        [
            ("Guadeloupe", "Île-de-France"),
            ("Martinique", "Provence-Alpes-Côte d'Azur"),
        ],
    )
    def test_overseas_not_in_metropolitan(
        self, dept: str, wrong_region: str
    ) -> None:
        """Test overseas departments are not in metropolitan regions."""
        assert is_dept_in_region(dept, wrong_region) is False

    @pytest.mark.parametrize("dept,region", CORSICA_DEPT_REGION_PAIRS)
    def test_corsica_departments(self, dept: str, region: str) -> None:
        """Test Corsica departments (special codes 2A and 2B)."""
        assert is_dept_in_region(dept, region) is True

    @pytest.mark.parametrize(
        "dept,wrong_region",
        [
            ("South Corsica", "Provence-Alpes-Côte d'Azur"),
            ("Upper Corsica", "Île-de-France"),
        ],
    )
    def test_corsica_not_in_other_regions(
        self, dept: str, wrong_region: str
    ) -> None:
        """Test Corsica departments are not in other regions."""
        assert is_dept_in_region(dept, wrong_region) is False

    @pytest.mark.parametrize(
        "invalid_dept,region",
        [
            ("InvalidDepartment", "Île-de-France"),
            ("NonExistent", "Grand Est"),
        ],
    )
    def test_invalid_department(self, invalid_dept: str, region: str) -> None:
        """Test that invalid department name returns False."""
        assert is_dept_in_region(invalid_dept, region) is False

    @pytest.mark.parametrize(
        "dept,invalid_region",
        [
            ("Paris", "InvalidRegion"),
            ("Ain", "NonExistentRegion"),
        ],
    )
    def test_invalid_region(self, dept: str, invalid_region: str) -> None:
        """Test that invalid region name returns False."""
        assert is_dept_in_region(dept, invalid_region) is False


class TestGetDeptName:
    """Test suite for get_dept_name function."""

    @pytest.mark.parametrize("code,expected_name", STANDARD_DEPT_CODES)
    def test_standard_codes(self, code: str, expected_name: str) -> None:
        """Test getting department names with standard codes."""
        assert get_dept_name(code) == expected_name

    @pytest.mark.parametrize(
        "code,expected_name",
        [
            ("2A", "South Corsica"),
            ("2B", "Upper Corsica"),
        ],
    )
    def test_corsica_codes(self, code: str, expected_name: str) -> None:
        """Test Corsica department codes (2A, 2B)."""
        assert get_dept_name(code) == expected_name

    @pytest.mark.parametrize("code,expected_name", OVERSEAS_DEPT_CODES)
    def test_overseas_codes(self, code: str, expected_name: str) -> None:
        """Test overseas territories codes."""
        assert get_dept_name(code) == expected_name

    @pytest.mark.parametrize("code,expected_name", SPECIAL_TERRITORY_CODES)
    def test_special_territories(self, code: str, expected_name: str) -> None:
        """Test special territories."""
        assert get_dept_name(code) == expected_name

    def test_foreign_code(self) -> None:
        """Test foreign code."""
        assert get_dept_name("99") == "Étranger"

    @pytest.mark.parametrize("invalid_code", ["999", "ABC", "00"])
    def test_invalid_code_raises_keyerror(self, invalid_code: str) -> None:
        """Test that invalid code raises KeyError."""
        with pytest.raises(KeyError):
            get_dept_name(invalid_code)
