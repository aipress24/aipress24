# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration test for OrganisationsExporter."""

from __future__ import annotations

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.views._export import MixedBWOrgExporter, OrganisationsExporter
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus


def test_organisations_exporter_includes_all_orgs_bw_first(db_session) -> None:
    org_no_bw = Organisation(name="BBB Org Without BW")
    db_session.add(org_no_bw)
    db_session.flush()

    user = User(email="owner@example.com")
    db_session.add(user)
    db_session.flush()

    org_with_bw = Organisation(name="AAA Org With BW")
    db_session.add(org_with_bw)
    db_session.flush()

    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        name="Media Wall",
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org_with_bw.id,
    )
    db_session.add(bw)
    db_session.flush()

    org_with_bw.bw_id = bw.id
    org_with_bw.bw_name = "Media BW name"
    org_with_bw.bw_active = "media"
    db_session.flush()

    org_inactive = Organisation(name="CCC Inactive Org", active=False)
    db_session.add(org_inactive)
    db_session.flush()

    exporter = OrganisationsExporter()
    fetched = exporter.fetch_data()

    # Ensure active orgs are returned and inactive org is excluded
    fetched_ids = [o.id for o in fetched]
    assert org_with_bw.id in fetched_ids
    assert org_no_bw.id in fetched_ids
    assert org_inactive.id not in fetched_ids

    # Ensure org WITH BW comes before org WITHOUT BW
    idx_with_bw = fetched_ids.index(org_with_bw.id)
    idx_no_bw = fetched_ids.index(org_no_bw.id)
    assert idx_with_bw < idx_no_bw

    assert exporter.cell_value(org_with_bw, "status") == "Actif"
    assert exporter.cell_value(org_with_bw, "has_bw") == "Oui"
    assert exporter.cell_value(org_with_bw, "bw_name") == "Media Wall"
    assert exporter.cell_value(org_with_bw, "bw_type") == "media"
    assert exporter.cell_value(org_with_bw, "bw_status") == BWStatus.ACTIVE.value
    assert exporter.cell_value(org_with_bw, "bw_id") == str(bw.id)

    assert exporter.cell_value(org_no_bw, "status") == "Actif"
    assert exporter.cell_value(org_no_bw, "has_bw") == "Non"
    assert exporter.cell_value(org_no_bw, "bw_name") == ""
    assert exporter.cell_value(org_no_bw, "bw_type") == ""
    assert exporter.cell_value(org_no_bw, "bw_status") == ""
    assert exporter.cell_value(org_no_bw, "bw_id") == ""


def test_mixed_exporter_sheets_populated(db_session) -> None:
    org = Organisation(name="Mixed Test Org")
    db_session.add(org)
    db_session.flush()

    user = User(email="mixeduser@example.com", organisation_id=org.id)
    db_session.add(user)
    db_session.flush()

    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        name="Mixed BW",
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()

    org.bw_id = bw.id
    db_session.flush()

    exporter = MixedBWOrgExporter()
    exporter.run()

    assert len(exporter.document) > 0
