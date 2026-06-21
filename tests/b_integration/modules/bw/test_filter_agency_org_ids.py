# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`filter_agency_org_ids` is the batched form of `is_organisation_an_agency`
— it must resolve a whole list of orgs to the agency subset in ONE
BusinessWall query (the wire Agences / Médias tabs called the per-org helper
in a loop → N+1)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import event

from app.flask.extensions import db
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus
from app.modules.bw.bw_activation.user_utils import filter_agency_org_ids

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _org_with_bw(db_session: Session, name: str, owner: User, type_media: str):
    org = Organisation(name=name, bw_active="media")
    db_session.add(org)
    db_session.flush()
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
        type_entreprise_media=type_media,
    )
    db_session.add(bw)
    db_session.flush()
    org.bw_id = bw.id
    db_session.flush()
    return org


def test_filter_agency_org_ids_is_batched(db_session: Session):
    owner = User(email="bwowner_agency@example.com", active=True)
    db_session.add(owner)
    db_session.flush()

    agencies = [
        _org_with_bw(db_session, f"Agence {i}", owner, "Agence de presse")
        for i in range(4)
    ]
    medias = [
        _org_with_bw(db_session, f"Media {i}", owner, "Journal") for i in range(3)
    ]
    orgs = agencies + medias

    bw_queries: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):
        if "bw_business_wall" in statement:
            bw_queries.append(statement)

    event.listen(db.engine, "before_cursor_execute", _capture)
    try:
        result = filter_agency_org_ids(orgs)
    finally:
        event.remove(db.engine, "before_cursor_execute", _capture)

    assert result == {o.id for o in agencies}
    # ONE batched query for all 7 orgs, not one per org.
    assert len(bw_queries) == 1, f"{len(bw_queries)} BW queries — N+1 regression"


def test_filter_agency_org_ids_empty():
    assert filter_agency_org_ids([]) == set()
