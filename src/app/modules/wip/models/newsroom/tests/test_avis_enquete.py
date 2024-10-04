# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.organisation import Organisation

from ..avis_enquete import AvisEnquete


def test_avis_enquete(db_session: scoped_session) -> None:
    assert isinstance(db_session, scoped_session)

    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")

    media = Organisation(name="Le Journal", owner=joe)

    db_session.add_all([joe, jim, media])
    db_session.flush()

    enquete = AvisEnquete()
    enquete.owner = joe
    enquete.media = media

    # FIXME
    enquete.commanditaire_id = jim.id

    enquete.date_debut_enquete = arrow.get("2022-01-01").datetime
    enquete.date_fin_enquete = arrow.get("2022-01-01").datetime
    enquete.date_bouclage = arrow.get("2022-01-01").datetime
    enquete.date_parution_prevue = arrow.get("2022-01-01").datetime

    db_session.add(enquete)
    db_session.flush()
