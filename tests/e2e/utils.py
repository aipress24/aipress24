# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from splinter import Browser

from app.models.auth import User
from app.models.content import Article


def create_stuff(db: SQLAlchemy) -> dict[str, User | Article]:
    owner = User(email="joe@example.com", id=0)
    db.session.add(owner)

    article = Article(owner=owner)
    db.session.add(article)
    db.session.commit()

    return {
        "user": owner,
        "article": article,
    }


def login(browser: Browser) -> None:
    browser.visit("/backdoor/press_media")
