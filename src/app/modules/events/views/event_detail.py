# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Event detail view."""

from __future__ import annotations

import json

from flask import Response, g, make_response, render_template, request

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.events import blueprint
from app.modules.events.models import EventPost
from app.modules.events.views._common import EventDetailVM
from app.modules.kyc.field_label import country_code_to_label, country_zip_code_to_city


@blueprint.route("/<int:id>")
@nav(parent="events")  # Parent is the events list page
def event(id: int):
    """Evénement"""
    event_obj = get_obj(id, EventPost)
    view_model = EventDetailVM(event_obj)

    # Set dynamic breadcrumb label
    g.nav.label = event_obj.title

    ctx = {
        "event": view_model,
        "metadata_list": _get_metadata_list(view_model),
        "title": event_obj.title,
        "related_events": [],
    }
    return render_template("pages/event.j2", **ctx)


@blueprint.route("/<int:id>", methods=["POST"])
@nav(hidden=True)
def event_post(id: int) -> Response | str:
    """Handle POST actions on event (like/unlike)."""
    event_obj = get_obj(id, EventPost)
    action = request.form.get("action", "")
    user = g.user

    match action:
        case "toggle-like":
            return _toggle_like(user, event_obj)
        case _:
            return ""


def _toggle_like(user: User, event_obj: EventPost) -> Response:
    """Toggle like status for an event."""
    # Lazy import to avoid circular import
    from app.services.social_graph import adapt

    social_user = adapt(user)

    if social_user.is_liking(event_obj):
        social_user.unlike(event_obj)
        message = f"Vous avec retiré votre 'like' au post {event_obj.title!r}"
    else:
        social_user.like(user, event_obj)
        message = f"Vous avez 'liké' le post {event_obj.title!r}"

    db.session.flush()
    event_obj.like_count = social_user.num_likes()
    db.session.commit()

    response = make_response(str(event_obj.like_count))
    response.headers["HX-Trigger"] = json.dumps({"showToast": message})
    return response


def _get_metadata_list(event_vm: EventDetailVM) -> list[dict]:
    """Build metadata list for event detail page."""
    item = event_vm
    data = [
        {
            "label": "Type d'événemant",
            "value": item.genre or "N/A",
            "href": "events",
        },
        {"label": "Secteur", "value": item.sector or "N/A", "href": "events"},
    ]

    if item.address:
        data.append({"label": "Adresse", "value": item.address, "href": "events"})
    if item.pays_zip_ville:
        data.append(
            {
                "label": "Pays",
                "value": country_code_to_label(item.pays_zip_ville),
                "href": "events",
            }
        )
    if item.pays_zip_ville_detail:
        data.append(
            {
                "label": "Ville",
                "value": country_zip_code_to_city(item.pays_zip_ville_detail),
                "href": "events",
            }
        )
    if item.url:
        data.append(
            {
                "label": "URL de l'événement",
                "value": item.url,
                "href": item.url,
            }
        )

    return data
