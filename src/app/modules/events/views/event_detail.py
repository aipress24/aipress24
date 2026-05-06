# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Event detail view."""

from __future__ import annotations

import json
from typing import ClassVar

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
from app.modules.events.services import (
    add_participant,
    can_user_accredit,
    is_participant,
    remove_participant,
)
from app.modules.events.views._common import EventDetailVM
from app.modules.kyc.field_label import country_code_to_label, country_zip_code_to_city
from app.modules.swork.models import Comment
from app.services.tracking import record_view


class EventDetailView(MethodView):
    """Event detail page with like/unlike action."""

    decorators: ClassVar[list] = [nav(parent="events", label="Événement")]

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
            "is_participating": is_participant(event_obj, g.user),
            "can_accredit": can_user_accredit(g.user, event_obj),
        }
        return render_template("pages/event.j2", **ctx)

    def post(self, id: int) -> Response | str:
        event_obj = get_obj(id, EventPost)
        action = request.form.get("action", "")
        user = g.user

        match action:
            case "toggle-like":
                response = self._toggle_like(user, event_obj)
                db.session.commit()
                return response
            case "post-comment":
                response = self._post_comment(event_obj)
                db.session.commit()
                return response
            case "toggle-participate":
                response = self._toggle_participate(user, event_obj)
                db.session.commit()
                return response
            case _:
                return ""

    def _toggle_like(self, user: User, event_obj: EventPost) -> Response:
        """Toggle like status for an event.

        Note: Does NOT commit - caller is responsible for committing.
        """
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

        response = make_response(str(event_obj.like_count))
        response.headers["HX-Trigger"] = json.dumps({"showToast": message})
        return response

    def _toggle_participate(self, user: User, event_obj: EventPost) -> Response:
        """Toggle the user's accreditation to an event.

        Bug 0127. Refuses with HTTP 403 when the user lacks the required role
        (journalists only). Otherwise toggles `participation_table` and
        returns the new button label so HTMX can swap it in place.

        Note: does NOT commit — caller is responsible.
        """
        if not can_user_accredit(user, event_obj):
            response = make_response("Accréditation réservée aux journalistes.", 403)
            return response

        if is_participant(event_obj, user):
            remove_participant(event_obj, user)
            new_label = "S'accréditer"
            toast_msg = f"Vous n'êtes plus accrédité à l'événement {event_obj.title!r}"
        else:
            add_participant(event_obj, user)
            new_label = "Annuler mon accréditation"
            toast_msg = f"Vous êtes accrédité à l'événement {event_obj.title!r}"

        response = make_response(new_label)
        response.headers["HX-Trigger"] = json.dumps({"showToast": toast_msg})
        return response

    def _post_comment(self, event_obj: EventPost) -> Response:
        """Post a comment on the event.

        Note: Does NOT commit - caller is responsible for committing.
        """
        user = g.user
        comment_text = request.form.get("comment", "").strip()
        if comment_text:
            comment = Comment()
            comment.content = comment_text
            comment.owner = user
            comment.object_id = f"event:{event_obj.id}"
            db.session.add(comment)
            event_obj.comment_count += 1
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
