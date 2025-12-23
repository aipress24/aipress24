# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin promotions views."""

from __future__ import annotations

from flask import redirect, render_template, request, url_for
from svcs.flask import container

from app.flask.lib.nav import nav
from app.logging import warn
from app.modules.admin import blueprint
from app.services.promotions import PromotionService

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


@blueprint.route("/promotions")
@nav(
    parent="index",
    icon="megaphone",
    label="Promotions",
)
def promotions():
    """Promotions management page."""
    promo_service = container.get(PromotionService)
    saved_slug = request.args.get("saved_promo")
    saved_body = ""
    promo_title = ""
    if saved_slug:
        promo = promo_service.get_promotion(slug=saved_slug)
        if promo:
            saved_body = promo.body
            promo_title = promo.title

    return render_template(
        "admin/pages/promotions.j2",
        title="Promotions",
        promo_options=PROMO_SLUG_LABEL,
        saved_slug=saved_slug,
        saved_body=saved_body,
        promo_title=promo_title,
    )


@blueprint.route("/promotions", methods=["POST"])
@nav(hidden=True)
def promotions_post():
    """Handle promotions form submission."""
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
    return redirect(url_for("admin.promotions", saved_promo=slug))
