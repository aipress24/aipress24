# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask, jsonify, redirect, request
from flask_classful import FlaskView, route
from flask_super.registry import register
from svcs.flask import container

from app.flask.lib.pages import page
from app.logging import warn
from app.services.promotions import PromotionService

from .base import BaseAdminPage
from .home import AdminHomePage

PROMO_SLUG_LABEL = [
    {"value": "wire-promo-1", "label": "Wire / promo 1"},
    {"value": "wire-promo-2", "label": "Wire / promo 2"},
    {"value": "events-promo-1", "label": "Events / promo 1"},
    {"value": "events-promo-2", "label": "Events / promo 2"},
    {"value": "biz-promo-1", "label": "Biz / promo 1"},
    {"value": "biz-promo-2", "label": "Biz / promo 2"},
    {"value": "swork-promo-1", "label": "Swork / promo 1"},
    {"value": "swork-promo-2", "label": "Swork / promo 2"},
]


@page
class AdminPromotionsPage(BaseAdminPage):
    name = "promotions"
    label = "Promotions"
    title = "Promotions"

    template = "admin/pages/promotions.j2"
    icon = "megaphone"

    parent = AdminHomePage

    def context(self):
        return {
            "promo_options": PROMO_SLUG_LABEL,
        }

    def post(self):
        data = dict(request.form)
        warn(data)

        promo_service = container.get(PromotionService)
        slug = data.get("promo", "")
        # title = data.get("title", "")
        title = ""
        body = data.get("content", "")
        warn(f"post {slug!r} {body!r}")
        if slug:
            promo_service.store_promotion(slug=slug, title=title, body=body)
        return redirect(self.url)


class LoadContentView(FlaskView):
    route_base = "/admin"

    @route("/promotions/load", methods=["POST"])
    def load_content(self):
        if not request.is_json:
            return jsonify(
                {
                    "success": False,
                    "message": "Requête invalide (JSON attendu).",
                }
            ), 400

        data = request.get_json()
        slug = data.get("promo_key")

        if not slug:
            return jsonify(
                {
                    "success": False,
                    "message": "Identifiant de promo manquant.",
                }
            ), 400

        promo_service = container.get(PromotionService)
        promo = promo_service.get_promotion(slug=slug)
        content = ""
        if promo:
            content = promo.body
        warn("slug:", slug, "content:", content)

        return jsonify({"success": True, "content": content})


@register
def register_on_app(app: Flask) -> None:
    LoadContentView.register(app)
