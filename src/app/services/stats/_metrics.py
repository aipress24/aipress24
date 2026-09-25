# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from arrow import Arrow
from flask_super.registry import register
from sqlalchemy import func, select

from app.flask.extensions import db
from app.models.content import BaseContent
from app.modules.wip.models import Article, Communique, Event, Sujet


class Metric:
    """Base class for something that can be measured."""

    id: str

    def compute(self, start_date: Arrow, end_date: Arrow) -> float:
        return 0


@register
class ActiveUsers(Metric):
    id = "active_users"


@register
class ActiveOrganisations(Metric):
    id = "active_organisations"


@register
class CountArticles(Metric):
    id = "count_articles"

    def compute(self, start_date, end_date) -> float:
        start = arrow.get(start_date)
        end = arrow.get(end_date)

        stmt = (
            select(func.count())
            .where(Article.created_at >= start)
            .where(Article.created_at <= end)
        )
        return float(db.session.scalar(stmt) or 0)


@register
class CountCommuniques(Metric):
    id = "count_communiques"

    def compute(self, start_date, end_date) -> float:
        start = arrow.get(start_date)
        end = arrow.get(end_date)

        stmt = (
            select(func.count())
            .where(Communique.created_at >= start)
            .where(Communique.created_at <= end)
        )
        return float(db.session.scalar(stmt) or 0)


@register
class CountEvents(Metric):
    id = "count_events"

    def compute(self, start_date, end_date) -> float:
        start = arrow.get(start_date)
        end = arrow.get(end_date)

        stmt = (
            select(func.count())
            .where(Event.created_at >= start)
            .where(Event.created_at <= end)
        )
        return float(db.session.scalar(stmt) or 0)


@register
class CountSujets(Metric):
    id = "count_sujets"

    def compute(self, start_date, end_date) -> float:
        start = arrow.get(start_date)
        end = arrow.get(end_date)

        stmt = (
            select(func.count())
            .where(Sujet.created_at >= start)
            .where(Sujet.created_at <= end)
        )
        return float(db.session.scalar(stmt) or 0)


@register
class CountContents(Metric):
    id = "count_contents"

    def compute(self, start_date, end_date) -> float:
        start = arrow.get(start_date)
        end = arrow.get(end_date)

        stmt = (
            select(func.count())
            .where(BaseContent.created_at >= start)
            .where(BaseContent.created_at <= end)
        )
        return float(db.session.scalar(stmt) or 0)
