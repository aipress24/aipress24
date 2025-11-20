# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for populate_profile module."""

from __future__ import annotations

import pytest
from app.enums import ContactTypeEnum
from app.modules.kyc.populate_profile import (
    default_business_wall,
    default_info_hobby,
    default_info_perso,
    default_info_pro,
    default_match_making,
    default_show_contact_details,
    populate_form_data,
    populate_json_field,
)


class TestDefaultShowContactDetails:
    """Test suite for default_show_contact_details function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = default_show_contact_details()
        assert isinstance(result, dict)

    def test_contains_email_keys_for_all_contact_types(self):
        """Test that all ContactTypeEnum values have email keys."""
        result = default_show_contact_details()

        for contact_type in ContactTypeEnum:
            email_key = f"email_{contact_type.name}"
            assert email_key in result
            assert result[email_key] is False

    def test_contains_mobile_keys_for_all_contact_types(self):
        """Test that all ContactTypeEnum values have mobile keys."""
        result = default_show_contact_details()

        for contact_type in ContactTypeEnum:
            mobile_key = f"mobile_{contact_type.name}"
            assert mobile_key in result
            assert result[mobile_key] is False

    def test_all_values_are_false(self):
        """Test that all values default to False."""
        result = default_show_contact_details()

        for value in result.values():
            assert value is False

    def test_returns_new_dict_each_time(self):
        """Test that each call returns a new dictionary instance."""
        result1 = default_show_contact_details()
        result2 = default_show_contact_details()

        assert result1 == result2
        assert result1 is not result2


class TestDefaultInfoPerso:
    """Test suite for default_info_perso function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = default_info_perso()
        assert isinstance(result, dict)

    def test_contains_expected_keys(self):
        """Test that all expected keys are present."""
        result = default_info_perso()
        expected_keys = {
            "pseudo",
            "no_carte_presse",
            "metier_principal",
            "metier_principal_detail",
            "metier",
            "metier_detail",
            "competences",
            "competences_journalisme",
            "langues",
            "formations",
            "experiences",
        }
        assert set(result.keys()) == expected_keys

    def test_string_fields_default_empty(self):
        """Test that string fields default to empty string."""
        result = default_info_perso()
        string_fields = ["pseudo", "no_carte_presse", "formations", "experiences"]

        for field in string_fields:
            assert result[field] == ""

    def test_list_fields_default_empty(self):
        """Test that list fields default to empty list."""
        result = default_info_perso()
        list_fields = [
            "metier_principal",
            "metier_principal_detail",
            "metier",
            "metier_detail",
            "competences",
            "competences_journalisme",
            "langues",
        ]

        for field in list_fields:
            assert result[field] == []

    def test_returns_new_dict_each_time(self):
        """Test that each call returns a new dictionary instance."""
        result1 = default_info_perso()
        result2 = default_info_perso()

        assert result1 == result2
        assert result1 is not result2


class TestDefaultInfoPro:
    """Test suite for default_info_pro function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = default_info_pro()
        assert isinstance(result, dict)

    def test_contains_expected_keys(self):
        """Test that all expected keys are present."""
        result = default_info_pro()
        expected_keys = {
            "nom_groupe_presse",
            "nom_media",
            "nom_media_instit",
            "type_entreprise_media",
            "type_presse_et_media",
            "nom_group_com",
            "nom_agence_rp",
            "type_agence_rp",
            "nom_adm",
            "nom_orga",
            "type_orga",
            "type_orga_detail",
            "taille_orga",
            "secteurs_activite_medias",
            "secteurs_activite_medias_detail",
            "secteurs_activite_rp",
            "secteurs_activite_rp_detail",
            "secteurs_activite_detailles",
            "secteurs_activite_detailles_detail",
            "pays_zip_ville",
            "pays_zip_ville_detail",
            "adresse_pro",
            "compl_adresse_pro",
            "email_relation_presse",
            "tel_standard",
            "ligne_directe",
            "url_site_web",
        }
        assert set(result.keys()) == expected_keys

    def test_string_fields_default_empty(self):
        """Test that string fields default to empty string."""
        result = default_info_pro()
        string_fields = [
            "nom_groupe_presse",
            "nom_media_instit",
            "nom_group_com",
            "nom_agence_rp",
            "nom_adm",
            "nom_orga",
            "taille_orga",
            "pays_zip_ville",
            "pays_zip_ville_detail",
            "adresse_pro",
            "compl_adresse_pro",
            "tel_standard",
            "ligne_directe",
            "url_site_web",
        ]

        for field in string_fields:
            assert result[field] == ""

    def test_list_fields_default_empty(self):
        """Test that list fields default to empty list."""
        result = default_info_pro()
        list_fields = [
            "nom_media",
            "type_entreprise_media",
            "type_presse_et_media",
            "type_agence_rp",
            "type_orga",
            "type_orga_detail",
            "secteurs_activite_medias",
            "secteurs_activite_medias_detail",
            "secteurs_activite_rp",
            "secteurs_activite_rp_detail",
            "secteurs_activite_detailles",
            "secteurs_activite_detailles_detail",
        ]

        for field in list_fields:
            assert result[field] == []


class TestDefaultMatchMaking:
    """Test suite for default_match_making function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = default_match_making()
        assert isinstance(result, dict)

    def test_contains_expected_keys(self):
        """Test that all expected keys are present."""
        result = default_match_making()
        expected_keys = {
            "fonctions_journalisme",
            "fonctions_pol_adm",
            "fonctions_pol_adm_detail",
            "fonctions_org_priv",
            "fonctions_org_priv_detail",
            "fonctions_ass_syn",
            "fonctions_ass_syn_detail",
            "interet_pol_adm",
            "interet_pol_adm_detail",
            "interet_org_priv",
            "interet_org_priv_detail",
            "interet_ass_syn",
            "interet_ass_syn_detail",
            "transformation_majeure",
            "transformation_majeure_detail",
        }
        assert set(result.keys()) == expected_keys

    def test_all_fields_default_empty_list(self):
        """Test that all fields default to empty list."""
        result = default_match_making()

        for value in result.values():
            assert value == []


class TestDefaultInfoHobby:
    """Test suite for default_info_hobby function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = default_info_hobby()
        assert isinstance(result, dict)

    def test_contains_expected_keys(self):
        """Test that all expected keys are present."""
        result = default_info_hobby()
        expected_keys = {
            "hobbies",
            "macaron_hebergement",
            "macaron_repas",
            "macaron_verre",
        }
        assert set(result.keys()) == expected_keys

    def test_hobbies_defaults_to_empty_string(self):
        """Test that hobbies field defaults to empty string."""
        result = default_info_hobby()
        assert result["hobbies"] == ""

    def test_macaron_fields_default_to_false(self):
        """Test that macaron fields default to False."""
        result = default_info_hobby()
        macaron_fields = ["macaron_hebergement", "macaron_repas", "macaron_verre"]

        for field in macaron_fields:
            assert result[field] is False


class TestDefaultBusinessWall:
    """Test suite for default_business_wall function."""

    def test_returns_dict(self):
        """Test that function returns a dictionary."""
        result = default_business_wall()
        assert isinstance(result, dict)

    def test_contains_expected_keys(self):
        """Test that all expected keys are present."""
        result = default_business_wall()
        expected_keys = {
            "trigger_media_agence_de_presse",
            "trigger_media_jr_microentrep",
            "trigger_media_media",
            "trigger_media_federation",
            "trigger_pr",
            "trigger_pr_independant",
            "trigger_pr_organisation",
            "trigger_organisation",
            "trigger_expert",
            "trigger_startup",
            "trigger_transformers",
            "trigger_transformers_independant",
            "trigger_academics",
            "trigger_academics_entrepreneur",
        }
        assert set(result.keys()) == expected_keys

    def test_all_triggers_default_to_false(self):
        """Test that all trigger fields default to False."""
        result = default_business_wall()

        for value in result.values():
            assert value is False


class TestPopulateJsonField:
    """Test suite for populate_json_field function."""

    def test_show_contact_details_category(self):
        """Test populating show_contact_details category."""
        results = {"email_PRESSE": True, "mobile_COMMUNICANT": True}
        populated = populate_json_field("show_contact_details", results)

        # Should have default structure with updated values
        assert populated["email_PRESSE"] is True
        assert populated["mobile_COMMUNICANT"] is True
        # Other values should remain default (False)
        assert populated["email_EXPERT"] is False

    def test_info_personnelle_category(self):
        """Test populating info_personnelle category."""
        results = {"pseudo": "test_user", "langues": ["fr", "en"]}
        populated = populate_json_field("info_personnelle", results)

        assert populated["pseudo"] == "test_user"
        assert populated["langues"] == ["fr", "en"]
        # Other values should remain default
        assert populated["no_carte_presse"] == ""
        assert populated["competences"] == []

    def test_info_professionnelle_category(self):
        """Test populating info_professionnelle category."""
        results = {"nom_groupe_presse": "Test Media", "nom_media": ["Magazine A"]}
        populated = populate_json_field("info_professionnelle", results)

        assert populated["nom_groupe_presse"] == "Test Media"
        assert populated["nom_media"] == ["Magazine A"]
        assert populated["nom_agence_rp"] == ""

    def test_match_making_category(self):
        """Test populating match_making category."""
        results = {"fonctions_journalisme": ["reporter"], "interet_pol_adm": ["policy"]}
        populated = populate_json_field("match_making", results)

        assert populated["fonctions_journalisme"] == ["reporter"]
        assert populated["interet_pol_adm"] == ["policy"]
        assert populated["fonctions_pol_adm"] == []

    def test_info_hobby_category(self):
        """Test populating info_hobby category."""
        results = {"hobbies": "photography", "macaron_repas": True}
        populated = populate_json_field("info_hobby", results)

        assert populated["hobbies"] == "photography"
        assert populated["macaron_repas"] is True
        assert populated["macaron_hebergement"] is False

    def test_business_wall_category(self):
        """Test populating business_wall category."""
        results = {"trigger_media_media": True, "trigger_expert": True}
        populated = populate_json_field("business_wall", results)

        assert populated["trigger_media_media"] is True
        assert populated["trigger_expert"] is True
        assert populated["trigger_pr"] is False

    def test_ignores_unknown_keys(self):
        """Test that unknown keys in results are ignored."""
        results = {"pseudo": "test", "unknown_field": "value", "another_unknown": 123}
        populated = populate_json_field("info_personnelle", results)

        assert populated["pseudo"] == "test"
        assert "unknown_field" not in populated
        assert "another_unknown" not in populated

    def test_empty_results_returns_defaults(self):
        """Test that empty results dict returns default values."""
        populated = populate_json_field("info_personnelle", {})

        default = default_info_perso()
        assert populated == default

    def test_invalid_category_raises_error(self):
        """Test that invalid category raises ValueError."""
        with pytest.raises(ValueError, match="Unknow category: invalid"):
            populate_json_field("invalid", {})


class TestPopulateFormData:
    """Test suite for populate_form_data function."""

    def test_show_contact_details_category(self):
        """Test populating show_contact_details data."""
        content = {"email_PRESSE": True}
        data: dict = {}

        populate_form_data("show_contact_details", content, data)

        # Should have all default keys plus updated values
        assert data["email_PRESSE"] is True
        assert data["mobile_PRESSE"] is False

    def test_info_personnelle_category(self):
        """Test populating info_personnelle data."""
        content = {"pseudo": "john_doe", "langues": ["fr"]}
        data: dict = {}

        populate_form_data("info_personnelle", content, data)

        assert data["pseudo"] == "john_doe"
        assert data["langues"] == ["fr"]
        assert data["formations"] == ""

    def test_info_professionnelle_category(self):
        """Test populating info_professionnelle data."""
        content = {"nom_groupe_presse": "Media Corp"}
        data: dict = {}

        populate_form_data("info_professionnelle", content, data)

        assert data["nom_groupe_presse"] == "Media Corp"
        assert data["nom_media"] == []

    def test_match_making_category(self):
        """Test populating match_making data."""
        content = {"fonctions_journalisme": ["editor"]}
        data: dict = {}

        populate_form_data("match_making", content, data)

        assert data["fonctions_journalisme"] == ["editor"]
        assert data["interet_pol_adm"] == []

    def test_info_hobby_category(self):
        """Test populating info_hobby data."""
        content = {"hobbies": "reading", "macaron_verre": True}
        data: dict = {}

        populate_form_data("info_hobby", content, data)

        assert data["hobbies"] == "reading"
        assert data["macaron_verre"] is True
        assert data["macaron_repas"] is False

    def test_business_wall_category(self):
        """Test populating business_wall data."""
        content = {"trigger_media_media": True}
        data: dict = {}

        populate_form_data("business_wall", content, data)

        assert data["trigger_media_media"] is True
        assert data["trigger_pr"] is False

    def test_updates_existing_data_dict(self):
        """Test that function updates existing data dictionary."""
        content = {"pseudo": "new_name"}
        data = {"existing_key": "existing_value"}

        populate_form_data("info_personnelle", content, data)

        assert data["existing_key"] == "existing_value"
        assert data["pseudo"] == "new_name"

    def test_content_overrides_defaults(self):
        """Test that content values override default values."""
        content = {"pseudo": "override", "langues": ["en", "es"]}
        data: dict = {}

        populate_form_data("info_personnelle", content, data)

        assert data["pseudo"] == "override"
        assert data["langues"] == ["en", "es"]

    def test_invalid_category_raises_error(self):
        """Test that invalid category raises ValueError."""
        data: dict = {}
        with pytest.raises(ValueError, match="Unknow category: invalid"):
            populate_form_data("invalid", {}, data)
