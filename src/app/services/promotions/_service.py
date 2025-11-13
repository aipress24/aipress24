# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from advanced_alchemy.exceptions import RepositoryError
from flask_super.decorators import service
from svcs.flask import container

from app.models.admin import Promotion

from ._models import PromotionRepository


@service
class PromotionService:
    """Service class for Promotion model."""

    def store_promotion(self, slug: str, title: str, body: str) -> Promotion:
        # def store_promotion(self, slug: str, title: str, body: str, profile: ProfileEnum | None = None) -> Promotion:

        repo = container.get(PromotionRepository)
        promo = repo.get_one_or_none(slug=slug)
        if promo is None:
            promo = Promotion(slug=slug, title=title, body=body, profile=None)
        else:
            promo.title = title
            promo.body = body

        promo = repo.add(promo)
        repo.session.flush()
        repo.session.commit()
        return promo

    def get_promotion(self, slug: str) -> Promotion | None:
        repo = container.get(PromotionRepository)
        try:
            return repo.get_one_or_none(slug=slug)
        except RepositoryError:
            return None
