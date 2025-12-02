# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC ontology loader.

These tests verify the transformation logic using direct function calls
and stubs instead of mocking internal functions.
"""

from __future__ import annotations

from app.modules.kyc.ontology_loader import (
    ONTOLOGY_DB_LIST,
    ONTOLOGY_MAP,
    to_label_value,
)


class TestToLabelValueDecorator:
    """Test suite for to_label_value decorator."""

    def test_transforms_list_to_tuples(self):
        """Test that decorator transforms list to (name, name) tuples."""

        @to_label_value
        def sample_func():
            return ["apple", "banana", "cherry"]

        result = sample_func()

        assert result == [
            ("apple", "apple"),
            ("banana", "banana"),
            ("cherry", "cherry"),
        ]

    def test_removes_duplicates(self):
        """Test that decorator removes duplicate values."""

        @to_label_value
        def with_duplicates():
            return ["apple", "banana", "apple", "cherry", "banana"]

        result = with_duplicates()

        assert len(result) == 3
        assert ("apple", "apple") in result
        assert ("banana", "banana") in result
        assert ("cherry", "cherry") in result

    def test_sorts_results(self):
        """Test that decorator sorts results alphabetically."""

        @to_label_value
        def unsorted():
            return ["zebra", "apple", "mango"]

        result = unsorted()

        assert result == [
            ("apple", "apple"),
            ("mango", "mango"),
            ("zebra", "zebra"),
        ]

    def test_handles_empty_list(self):
        """Test that decorator handles empty list."""

        @to_label_value
        def empty():
            return []

        result = empty()

        assert result == []

    def test_combined_dedup_and_sort(self):
        """Test combined deduplication and sorting."""

        @to_label_value
        def mixed():
            return ["Zebra", "apple", "Zebra", "mango", "apple"]

        result = mixed()

        # Should be sorted (case-sensitive) and deduplicated
        assert len(result) == 3
        # Capital Z comes before lowercase a in ASCII sort
        assert result[0][0] == "Zebra"


class TestOntologyMappings:
    """Test suite verifying ontology mapping structure."""

    def test_ontology_map_has_expected_keys(self):
        """Test that ONTOLOGY_MAP contains expected field type keys."""
        expected_keys = [
            "list_civilite",
            "multi_type_entreprise_medias",
            "multi_type_media",
            "multi_fonctions_journalisme",
            "multi_type_agences_rp",
            "multidual_type_orga",
            "list_taille_orga",
            "country_pays",
            "multidual_secteurs_detail",
            "multi_langues",
        ]
        for key in expected_keys:
            assert key in ONTOLOGY_MAP, f"Missing key: {key}"

    def test_ontology_map_values_are_strings(self):
        """Test that all ONTOLOGY_MAP values are strings."""
        for key, value in ONTOLOGY_MAP.items():
            assert isinstance(value, str), f"Value for {key} is not a string"

    def test_ontology_db_list_contains_expected_ontologies(self):
        """Test that ONTOLOGY_DB_LIST contains expected ontology names."""
        expected_ontologies = [
            "civilite",
            "competence_expert",
            "journalisme_competence",
            "journalisme_fonction",
            "langue",
            "media_type",
            "type_entreprises_medias",
            "orga_newsrooms",
            "taille_organisation",
            "type_agence_rp",
        ]
        for ontology in expected_ontologies:
            assert ontology in ONTOLOGY_DB_LIST, f"Missing ontology: {ontology}"


class TestOntologyMapLogic:
    """Test suite verifying ONTOLOGY_MAP logic patterns."""

    def test_list_prefixed_fields_map_to_simple_taxonomies(self):
        """Verify list_ prefixed fields map to simple taxonomy names."""
        list_fields = [k for k in ONTOLOGY_MAP if k.startswith("list_")]
        for field in list_fields:
            value = ONTOLOGY_MAP[field]
            assert isinstance(value, str)
            assert "_" in value or value.isalpha()

    def test_multi_prefixed_fields_exist(self):
        """Verify multi_ prefixed fields are present."""
        multi_fields = [k for k in ONTOLOGY_MAP if k.startswith("multi_")]
        assert len(multi_fields) > 0

    def test_multidual_prefixed_fields_exist(self):
        """Verify multidual_ prefixed fields are present."""
        multidual_fields = [k for k in ONTOLOGY_MAP if k.startswith("multidual_")]
        assert len(multidual_fields) > 0

    def test_country_field_maps_to_pays(self):
        """Verify country_pays maps to 'pays' ontology."""
        assert ONTOLOGY_MAP.get("country_pays") == "pays"
