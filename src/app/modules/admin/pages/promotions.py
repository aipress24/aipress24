# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask, jsonify, redirect, request, url_for
from flask_classful import FlaskView, route
from flask_super.registry import register
from svcs.flask import container

from app.logging import warn
from app.services.promotions import PromotionService

from .base import BaseAdminPage
from .home import AdminHomePage

PROMO_SLUG_LABEL = [
    {"value": "wire/1", "label": "Wire / promo 1"},
    {"value": "wire/2", "label": "Wire / promo 2"},
    {"value": "events/1", "label": "Events / promo 1"},
    {"value": "events/2", "label": "Events / promo 2"},
    {"value": "biz/1", "label": "Biz / promo 1"},
    {"value": "biz/2", "label": "Biz / promo 2"},
    {"value": "swork/1", "label": "Swork / promo 1"},
    {"value": "swork/2", "label": "Swork / promo 2"},
]

BOX_TITLE1 = "AiPRESS24 vous informe"
BOX_TITLE2 = "AiPRESS24 vous suggère"


# Note: Route now handled by views_pages.py
class AdminPromotionsPage(BaseAdminPage):
    name = "promotions"
    label = "Promotions"
    title = "Promotions"

    template = "admin/pages/promotions.j2"
    icon = "megaphone"

    parent = AdminHomePage

    def context(self):
        promo_service = container.get(PromotionService)
        saved_slug = request.args.get("saved_promo")
        saved_body = ""
        promo_title = ""
        if saved_slug:
            promo = promo_service.get_promotion(slug=saved_slug)
            if promo:
                saved_body = promo.body
                promo_title = promo.title

        return {
            "promo_options": PROMO_SLUG_LABEL,
            "saved_slug": saved_slug,  # Used to pre-select the dropdown
            "saved_body": saved_body,
            "promo_title": promo_title,
        }

    def post(self):
        data = dict(request.form)
        warn(data)

        promo_service = container.get(PromotionService)
        slug = data.get("promo", "")
        if slug.endswith("1"):
            title = BOX_TITLE1
        else:
            title = BOX_TITLE2
        body = data.get("content", "")
        warn(f"post {slug!r} {body!r}")
        if slug:
            promo_service.store_promotion(slug=slug, title=title, body=body)
            redirect(url_for("admin.promotions", saved_promo=slug))
        return redirect(url_for("admin.promotions", saved_promo=slug))


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
            warn("Identifiant de promo manquant.")
            return jsonify(
                {
                    "success": False,
                    "message": "Identifiant de promo manquant.",
                }
            ), 400

        promo_service = container.get(PromotionService)
        promo = promo_service.get_promotion(slug=slug)
        content = ""
        promo_title = ""
        warn("promo", promo)

        if promo:
            promo_title = promo.title
            content = promo.body
        warn("loading slug:", slug, "content:", content, "promo_title", promo_title)

        return jsonify(
            {
                "success": True,
                "content": content,
                "promo_title": promo_title,
            }
        )


@register
def register_on_app(app: Flask) -> None:
    LoadContentView.register(app)
