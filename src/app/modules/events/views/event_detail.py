# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Event detail view."""

from __future__ import annotations

import json

from flask import flash, g, make_response, redirect, render_template, request
from flask.views import MethodView
from werkzeug import Response

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.events import blueprint
from app.modules.events.models import EventPost
from app.modules.events.views._common import EventDetailVM
from app.modules.kyc.field_label import country_code_to_label, country_zip_code_to_city
from app.modules.swork.models import Comment
from app.services.tracking import record_view


class EventDetailView(MethodView):
    """Event detail page with like/unlike action."""

    decorators = [nav(parent="events", label="Événement")]

    def get(self, id: int):
        event_obj = get_obj(id, EventPost)
        view_model = EventDetailVM(event_obj)

        # Record view
        record_view(g.user, event_obj)
        db.session.commit()

        # Set dynamic breadcrumb label
        g.nav.label = event_obj.title

        ctx = {
            "event": view_model,
            "metadata_list": self._get_metadata_list(view_model),
            "title": event_obj.title,
            "related_events": [],
        }
        return render_template("pages/event.j2", **ctx)

    def post(self, id: int) -> Response | str:
        event_obj = get_obj(id, EventPost)
        action = request.form.get("action", "")
        user = g.user

        match action:
            case "toggle-like":
                return self._toggle_like(user, event_obj)
            case "post-comment":
                return self._post_comment(event_obj)
            case _:
                return ""

    def _toggle_like(self, user: User, event_obj: EventPost) -> Response:
        """Toggle like status for an event."""
        from app.services.social_graph import adapt

        social_user = adapt(user)
        social_content = adapt(event_obj)

        if social_user.is_liking(event_obj):
            social_user.unlike(event_obj)
            message = (
                f"Vous avez retiré votre 'like' de l'événement {event_obj.title!r}"
            )
        else:
            social_user.like(event_obj)
            message = f"Vous avez 'liké' l'événement {event_obj.title!r}"

        db.session.flush()
        event_obj.like_count = social_content.num_likes()
        db.session.commit()

        response = make_response(str(event_obj.like_count))
        response.headers["HX-Trigger"] = json.dumps({"showToast": message})
        return response

    def _post_comment(self, event_obj: EventPost) -> Response:
        """Post a comment on the event."""
        user = g.user
        comment_text = request.form.get("comment", "").strip()
        if comment_text:
            comment = Comment()
            comment.content = comment_text
            comment.owner = user
            comment.object_id = f"event:{event_obj.id}"
            db.session.add(comment)
            event_obj.comment_count += 1
            db.session.commit()
            flash("Votre commentaire a été posté.")

        return redirect(url_for(event_obj) + "#comments-title")

    def _get_metadata_list(self, event_vm: EventDetailVM) -> list[dict]:
        """Build metadata list for event detail page."""
        item = event_vm
        data = [
            {
                "label": "Type d'événement",
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


# Register the view
blueprint.add_url_rule("/<int:id>", view_func=EventDetailView.as_view("event"))
