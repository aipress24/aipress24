# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.organisation import Organisation

from ..article import Article


def test_article(db_session: scoped_session) -> None:
    assert isinstance(db_session, scoped_session)

    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")

    media = Organisation(name="Le Journal", owner=joe)

    db_session.add_all([joe, jim, media])
    db_session.flush()

    article = Article(owner=jim, media=media)
    article.date_parution_prevue = arrow.get("2022-01-01").datetime
    article.date_publication_aip24 = arrow.get("2022-01-01").datetime
    article.date_paiement = arrow.get("2022-01-01").datetime

    # FIXME
    article.commanditaire_id = joe.id

    db_session.add(article)
    db_session.flush()
