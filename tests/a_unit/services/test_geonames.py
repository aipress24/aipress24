# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pytest

from app.services.geonames._service import get_dept_name, is_dept_in_region


def test_is_dept_in_region() -> None:
    assert is_dept_in_region("Paris", "Île-de-France")
    assert is_dept_in_region("Ain", "Auvergne-Rhône-Alpes")
    assert is_dept_in_region("Aisne", "Hauts-de-France")
    assert is_dept_in_region("Allier", "Auvergne-Rhône-Alpes")
    assert is_dept_in_region("Alpes-de-Haute-Provence", "Provence-Alpes-Côte d'Azur")
    assert is_dept_in_region("Hautes-Alpes", "Provence-Alpes-Côte d'Azur")
    assert is_dept_in_region("Alpes-Maritimes", "Provence-Alpes-Côte d'Azur")
    assert is_dept_in_region("Ardèche", "Auvergne-Rhône-Alpes")
    assert is_dept_in_region("Ardennes", "Grand Est")
    assert is_dept_in_region("Ariège", "Occitanie")
    assert is_dept_in_region("Aube", "Grand Est")
    assert is_dept_in_region("Aude", "Occitanie")
    assert is_dept_in_region("Aveyron", "Occitanie")
    assert is_dept_in_region("Bouches-du-Rhône", "Provence-Alpes-Côte d'Azur")
    assert is_dept_in_region("Calvados", "Normandie")

    assert not is_dept_in_region("Calvados", "Île-de-France")
    assert not is_dept_in_region("Ain", "Normandie")
    assert not is_dept_in_region("Aisne", "Auvergne-Rhône-Alpes")
    assert not is_dept_in_region("Allier", "Hauts-de-France")
    assert not is_dept_in_region("Alpes-de-Haute-Provence", "Auvergne-Rhône-Alpes")


def test_is_dept_in_region_invalid_department() -> None:
    """Test that invalid department name returns False."""
    assert not is_dept_in_region("InvalidDepartment", "Île-de-France")
    assert not is_dept_in_region("NonExistent", "Grand Est")


def test_is_dept_in_region_invalid_region() -> None:
    """Test that invalid region name returns False."""
    assert not is_dept_in_region("Paris", "InvalidRegion")
    assert not is_dept_in_region("Ain", "NonExistentRegion")


def test_is_dept_in_region_overseas() -> None:
    """Test overseas departments and territories."""
    assert is_dept_in_region("Guadeloupe", "Guadeloupe")
    assert is_dept_in_region("Martinique", "Martinique")
    assert is_dept_in_region("Guyane", "Guyane")
    assert is_dept_in_region("La Réunion", "La Réunion")
    assert is_dept_in_region("Mayotte", "Mayotte")

    # These should not be in metropolitan regions
    assert not is_dept_in_region("Guadeloupe", "Île-de-France")
    assert not is_dept_in_region("Martinique", "Provence-Alpes-Côte d'Azur")


def test_is_dept_in_region_corsica() -> None:
    """Test Corsica departments (special codes 2A and 2B)."""
    assert is_dept_in_region("South Corsica", "Corse")
    assert is_dept_in_region("Upper Corsica", "Corse")

    assert not is_dept_in_region("South Corsica", "Provence-Alpes-Côte d'Azur")
    assert not is_dept_in_region("Upper Corsica", "Île-de-France")


class TestGetDeptName:
    """Test suite for get_dept_name function."""

    def test_get_dept_name_standard_codes(self) -> None:
        """Test getting department names with standard codes."""
        assert get_dept_name("01") == "Ain"
        assert get_dept_name("75") == "Paris"
        assert get_dept_name("13") == "Bouches-du-Rhône"
        assert get_dept_name("59") == "Nord"
        assert get_dept_name("33") == "Gironde"

    def test_get_dept_name_corsica(self) -> None:
        """Test Corsica department codes (2A, 2B)."""
        assert get_dept_name("2A") == "South Corsica"
        assert get_dept_name("2B") == "Upper Corsica"

    def test_get_dept_name_overseas(self) -> None:
        """Test overseas territories codes."""
        assert get_dept_name("971") == "Guadeloupe"
        assert get_dept_name("972") == "Martinique"
        assert get_dept_name("973") == "Guyane"
        assert get_dept_name("974") == "La Réunion"
        assert get_dept_name("976") == "Mayotte"

    def test_get_dept_name_special_territories(self) -> None:
        """Test special territories."""
        assert get_dept_name("977") == "Saint-Barthélemy"
        assert get_dept_name("978") == "Saint-Martin"
        assert get_dept_name("988") == "Nouvelle-Calédonie"
        assert get_dept_name("989") == "Île de Clipperton"

    def test_get_dept_name_foreign(self) -> None:
        """Test foreign code."""
        assert get_dept_name("99") == "Étranger"

    def test_get_dept_name_invalid_code(self) -> None:
        """Test that invalid code raises KeyError."""
        with pytest.raises(KeyError):
            get_dept_name("999")

        with pytest.raises(KeyError):
            get_dept_name("ABC")

        with pytest.raises(KeyError):
            get_dept_name("00")
