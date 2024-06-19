# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from ._service import is_dept_in_region


def test_is_dept_in_region():
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
