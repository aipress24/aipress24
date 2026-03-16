# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for BusinessWall model."""

from __future__ import annotations

from app.modules.bw.bw_activation.models.business_wall import BusinessWall


class TestUpdateLocationFields:
    """Tests for BusinessWall.update_location_fields() method."""

    def test_update_location_fields_french_format_2_parts(self):
        bw = BusinessWall()
        bw.pays_zip_ville = "FRA"
        bw.pays_zip_ville_detail = f"{'FRA / 17000 La Rochelle'}"

        bw.update_location_fields()

        assert bw.code_postal == "17000"
        assert bw.departement == "17"
        assert bw.ville == "La Rochelle"

    def test_update_location_fields_french_format_3_parts(self):
        bw = BusinessWall()
        bw.pays_zip_ville = "FRA"
        bw.pays_zip_ville_detail = "FRA / 13001 Aix en Provence"

        bw.update_location_fields()

        assert bw.code_postal == "13001"
        assert bw.departement == "13"
        assert bw.ville == "Aix en Provence"

    def test_update_location_fields_paris(self):
        bw = BusinessWall()
        bw.pays_zip_ville = "FRA"
        bw.pays_zip_ville_detail = "FRA / 75001 Paris"

        bw.update_location_fields()

        assert bw.code_postal == "75001"
        assert bw.departement == "75"
        assert bw.ville == "Paris"

    def test_update_location_fields_non_french(self):
        bw = BusinessWall()
        bw.pays_zip_ville = "GBR"
        bw.pays_zip_ville_detail = "GBR / SW1A 1AA London"

        bw.update_location_fields()

        assert bw.code_postal == "SW1A"
        assert bw.departement == ""  # No departement
        assert bw.ville == "1AA London"

    def test_update_location_fields_empty(self):
        bw = BusinessWall()
        bw.pays_zip_ville = ""
        bw.pays_zip_ville_detail = ""

        bw.update_location_fields()

        assert bw.code_postal is None
        assert bw.departement is None
        assert bw.ville is None
