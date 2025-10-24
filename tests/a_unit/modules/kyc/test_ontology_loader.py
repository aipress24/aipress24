# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for KYC ontology loader."""

from __future__ import annotations

from unittest.mock import patch

from app.modules.kyc.ontology_loader import (
    get_choices,
    get_ontology_content,
    nom_agence_rp_choices,
    nom_media_choices,
    nom_media_instit_choices,
    nom_orga_choices,
    to_label_value,
    zip_code_city_list,
)


def test_to_label_value():
    """Test to_label_value decorator."""

    def test_func():
        return ["apple", "banana", "apple", "cherry"]

    decorated = to_label_value(test_func)
    result = decorated()

    # Should return sorted unique values as (name, name) tuples
    assert result == [("apple", "apple"), ("banana", "banana"), ("cherry", "cherry")]


@patch("app.modules.kyc.ontology_loader.get_taxonomy")
@patch("app.modules.kyc.ontology_loader.get_organisation_for_noms_medias")
def test_nom_media_choices(mock_get_orgs, mock_get_tax):
    """Test nom_media_choices function."""
    mock_get_tax.return_value = ["NewsRoom1", "NewsRoom2"]
    mock_get_orgs.return_value = ["Media1", "Media2"]

    result = nom_media_choices()

    # Should combine and convert to label-value tuples
    assert len(result) == 4
    assert ("Media1", "Media1") in result
    assert ("NewsRoom1", "NewsRoom1") in result


@patch("app.modules.kyc.ontology_loader.get_taxonomy")
@patch("app.modules.kyc.ontology_loader.get_organisation_for_noms_orgas")
def test_nom_media_instit_choices(mock_get_orgs, mock_get_tax):
    """Test nom_media_instit_choices function."""
    mock_get_tax.return_value = ["Group1"]
    mock_get_orgs.return_value = ["Org1", "Org2"]

    result = nom_media_instit_choices()

    assert len(result) == 3
    assert ("Group1", "Group1") in result
    assert ("Org1", "Org1") in result


@patch("app.modules.kyc.ontology_loader.get_taxonomy")
@patch("app.modules.kyc.ontology_loader.get_organisation_for_noms_com")
def test_nom_agence_rp_choices(mock_get_orgs, mock_get_tax):
    """Test nom_agence_rp_choices function."""
    mock_get_tax.return_value = ["Agency1"]
    mock_get_orgs.return_value = ["ComOrg1"]

    result = nom_agence_rp_choices()

    assert len(result) == 2
    assert ("Agency1", "Agency1") in result
    assert ("ComOrg1", "ComOrg1") in result


@patch("app.modules.kyc.ontology_loader.get_taxonomy")
@patch("app.modules.kyc.ontology_loader.get_organisation_for_noms_orgas")
def test_nom_orga_choices(mock_get_orgs, mock_get_tax):
    """Test nom_orga_choices function."""
    mock_get_tax.return_value = ["Group1"]
    mock_get_orgs.return_value = ["Org1"]

    result = nom_orga_choices()

    assert len(result) == 2
    assert ("Group1", "Group1") in result
    assert ("Org1", "Org1") in result


@patch("app.modules.kyc.ontology_loader.get_full_countries")
def test_get_ontology_content_pays(mock_countries):
    """Test get_ontology_content for 'pays'."""
    # Clear cache first since get_ontology_content uses @functools.cache
    get_ontology_content.cache_clear()

    mock_countries.return_value = [("FR", "France"), ("US", "USA")]

    result = get_ontology_content("pays")

    assert result == [("FR", "France"), ("US", "USA")]
    mock_countries.assert_called_once()


@patch("app.modules.kyc.ontology_loader.get_full_taxonomy")
def test_get_ontology_content_db_list(mock_tax):
    """Test get_ontology_content for ontology in ONTOLOGY_DB_LIST."""
    # Clear cache first since get_ontology_content uses @functools.cache
    get_ontology_content.cache_clear()

    mock_tax.return_value = [("civ1", "Civilité 1")]

    result = get_ontology_content("civilite")

    assert result == [("civ1", "Civilité 1")]
    mock_tax.assert_called_once_with("civilite")


@patch("app.modules.kyc.ontology_loader.get_taxonomy_dual_select")
def test_get_ontology_content_dual_select(mock_dual):
    """Test get_ontology_content for dual select taxonomies."""
    mock_dual.return_value = {"cat1": ["item1", "item2"]}

    result = get_ontology_content("secteur_detaille")

    assert result == {"cat1": ["item1", "item2"]}
    mock_dual.assert_called_once_with("secteur_detaille")


@patch("app.modules.kyc.ontology_loader.get_ontology_content")
def test_get_choices_with_ontology_map(mock_get_onto):
    """Test get_choices when field_type is in ONTOLOGY_MAP."""
    mock_get_onto.return_value = [("lang1", "Language 1")]

    result = get_choices("multi_langues")

    assert result == [("lang1", "Language 1")]
    mock_get_onto.assert_called_once_with("langue")


@patch("app.modules.kyc.ontology_loader.nom_agence_rp_choices")
def test_get_choices_with_org_name(mock_choices):
    """Test get_choices for organization name fields."""
    mock_choices.return_value = [("Agency1", "Agency1")]

    result = get_choices("listfree_nom_agence_rp")

    assert result == [("Agency1", "Agency1")]
    mock_choices.assert_called_once()


@patch("app.modules.kyc.ontology_loader.nom_media_choices")
def test_get_choices_newsrooms(mock_choices):
    """Test get_choices for newsrooms field."""
    mock_choices.return_value = [("Room1", "Room1")]

    result = get_choices("multifree_newsrooms")

    assert result == [("Room1", "Room1")]
    mock_choices.assert_called_once()


@patch("app.modules.kyc.ontology_loader.get_zip_code_country")
def test_zip_code_city_list(mock_zip):
    """Test zip_code_city_list function."""
    mock_zip.return_value = [
        {"value": "FR / 75001", "label": "Paris"},
        {"value": "FR / 69001", "label": "Lyon"},
    ]

    result = zip_code_city_list("FR")

    assert len(result) == 2
    assert result[0]["label"] == "Paris"
    mock_zip.assert_called_once_with("FR")
