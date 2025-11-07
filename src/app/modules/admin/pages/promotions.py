# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask, jsonify, request
from flask_classful import FlaskView, route
from flask_super.registry import register

from app.flask.lib.pages import page
from app.logging import warn

from .base import BaseAdminPage
from .home import AdminHomePage

PROMO_CONTENT_DB = {
    "wire-promo-1": "Wire / promo 1",
    "wire-promo-2": "Wire / promo 2",
    "events-promo-1": "Events / promo 1",
    "events-promo-2": "Events / promo 2",
    "biz-promo-1": "Biz / promo 1",
    "biz-promo-2": "Biz / promo 2",
    "swork-promo-1": "Swork / promo 1",
    "swork-promo-2": "Swork / promo 2",
}

PROMO_OPTIONS = [
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
            "promo_options": PROMO_OPTIONS,
        }

    def post(self) -> None:
        data = dict(request.form)
        warn(data)


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
        promo_key = data.get("promo_key")

        if not promo_key:
            return jsonify(
                {"success": False, "message": "Identifiant de promo manquant."}
            ), 400

        content = "test data"
        # content = get(promo_key) or ""
        return jsonify({"success": True, "content": content})


@register
def register_on_app(app: Flask) -> None:
    LoadContentView.register(app)
