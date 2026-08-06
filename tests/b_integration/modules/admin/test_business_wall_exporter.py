# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration test for BusinessWallExporter."""

from __future__ import annotations

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.views._export import BusinessWallExporter
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus
from app.modules.kyc.field_label import country_code_to_country_name
from app.modules.kyc.ontology_loader import get_ontology_content
from app.services.zip_codes import CountryEntry


def test_business_wall_exporter(db_session) -> None:
    get_ontology_content.cache.clear()
    country_code_to_country_name.cache_clear()
    c_fra = CountryEntry(iso3="FRA", name="France", seq=1)
    c_bel = CountryEntry(iso3="BEL", name="Belgique", seq=2)
    db_session.add_all([c_fra, c_bel])
    db_session.flush()

    user = User(email="bwowner@example.com")
    db_session.add(user)
    db_session.flush()

    org = Organisation(name="Test Org for BW")
    db_session.add(org)
    db_session.flush()

    bw_b = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        name="B Wall",
        name_entity="Entity B",
        name_official="Official B",
        name_group="Group B",
        name_institution="Inst B",
        type_organisation=["entreprise_media"],
        type_entreprise_media=["presse_en_ligne"],
        type_presse_et_media=["pqr"],
        taille_orga="10_49",
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org.id,
        pays_zip_ville_detail="FRA / 75001 Paris",
        pays_zip_ville="FRA",
    )
    bw_a = BusinessWall(
        bw_type="pr",
        status=BWStatus.ACTIVE.value,
        name="A Wall",
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org.id,
        pays_zip_ville_detail="BEL / 1000 Bruxelles",
        pays_zip_ville="BEL",
    )
    bw_draft = BusinessWall(
        bw_type="micro",
        status=BWStatus.DRAFT.value,
        name="Draft Wall",
        owner_id=user.id,
        payer_id=user.id,
    )

    db_session.add_all([bw_b, bw_a, bw_draft])
    db_session.flush()

    exporter = BusinessWallExporter()
    fetched = exporter.fetch_data()

    fetched_ids = [bw.id for bw in fetched]
    assert bw_a.id in fetched_ids
    assert bw_b.id in fetched_ids
    assert bw_draft.id not in fetched_ids

    # Sorted by name (A Wall before B Wall)
    assert fetched_ids.index(bw_a.id) < fetched_ids.index(bw_b.id)

    # Check cell_value formatting
    assert exporter.cell_value(bw_b, "organisation_id") == str(org.id)
    assert isinstance(exporter.cell_value(bw_b, "organisation_id"), str)

    assert exporter.cell_value(bw_b, "name") == "B Wall"
    assert exporter.cell_value(bw_b, "name_entity") == "Entity B"
    assert exporter.cell_value(bw_b, "name_official") == "Official B"
    assert exporter.cell_value(bw_b, "name_group") == "Group B"
    assert exporter.cell_value(bw_b, "name_institution") == "Inst B"

    bw_b.secteurs_activite = ["batiment", "informatique"]
    db_session.flush()

    assert "secteurs_activite" in exporter.columns
    idx_type_org = exporter.columns.index("type_organisation")
    idx_secteurs = exporter.columns.index("secteurs_activite")
    assert idx_secteurs == idx_type_org + 1

    assert "count_bw_members" in exporter.columns
    idx_press_type = exporter.columns.index("type_presse_et_media")
    idx_members = exporter.columns.index("count_bw_members")
    assert idx_members == idx_press_type + 1

    assert "bwmi" in exporter.columns
    assert "bwpri" in exporter.columns
    assert "pr_agency" in exporter.columns
    assert "bwpre" in exporter.columns
    idx_payer = exporter.columns.index("payer_email")
    assert exporter.columns.index("bwmi") == idx_payer + 1
    assert exporter.columns.index("bwpri") == idx_payer + 2
    assert exporter.columns.index("pr_agency") == idx_payer + 3
    assert exporter.columns.index("bwpre") == idx_payer + 4

    assert exporter.cell_value(bw_b, "type_organisation") == "entreprise_media"
    assert exporter.cell_value(bw_b, "secteurs_activite") == "batiment, informatique"
    assert exporter.cell_value(bw_b, "type_entreprise_media") == "presse_en_ligne"
    assert exporter.cell_value(bw_b, "type_presse_et_media") == "pqr"
    assert exporter.cell_value(bw_b, "count_bw_members") == 1
    assert exporter.cell_value(bw_b, "taille_orga") == "10_49"
    assert exporter.cell_value(bw_b, "bwmi") == ""
    assert exporter.cell_value(bw_b, "bwpri") == ""
    assert exporter.cell_value(bw_b, "pr_agency") == ""
    assert exporter.cell_value(bw_b, "bwpre") == ""

    assert exporter.cell_value(bw_b, "pays") == "France"
    assert exporter.cell_value(bw_b, "code_postal_ville") == "FRA / 75001 Paris"

    assert exporter.cell_value(bw_a, "pays") == "Belgique"
    assert exporter.cell_value(bw_a, "code_postal_ville") == "BEL / 1000 Bruxelles"
