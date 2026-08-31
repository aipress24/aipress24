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

from app.enums import MODE_LABELS
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.flask.sqla import get_public_obj
from app.models.auth import User
from app.modules.events import blueprint
from app.modules.events.models import AccreditationStatus, EventPost
from app.modules.events.pricing import price_label
from app.modules.events.services import (
    AccreditationClosedError,
    get_accreditation,
    is_open,
    request_accreditation,
    sees_access_details,
    sees_full_content,
    withdraw_accreditation,
)
from app.modules.events.views._common import EventDetailVM
from app.modules.kyc.field_label import country_code_to_label, country_zip_code_to_city
from app.modules.swork.models import Comment
from app.services.tracking import record_view


def _accreditation_status(event: EventPost, user: User) -> str:
    """L'état de la demande du membre, sous forme de chaîne pour le
    gabarit : `""`, `requested`, `accepted`, `rejected` ou `withdrawn`.

    Une chaîne vide vaut « aucune demande » — le membre voit le bouton.
    `withdrawn` s'affiche comme une absence de demande : s'être
    désinscrit n'interdit pas de revenir (RG-03).
    """
    accreditation = get_accreditation(event, user)
    if accreditation is None:
        return ""
    if accreditation.status == AccreditationStatus.WITHDRAWN:
        return ""
    return str(accreditation.status.value)


class EventDetailView(MethodView):
    """Event detail page with like/unlike action."""

    decorators: ClassVar[list] = [nav(parent="events", label="Événement")]

    def get(self, id: int):
        event_obj = get_public_obj(id, EventPost)
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
            "accreditation": _accreditation_status(event_obj, g.user),
            "sees_content": sees_full_content(g.user, event_obj),
            "audience": event_obj.audience or [],
            "is_open": is_open(event_obj),
            "sees_access_details": sees_access_details(g.user, event_obj),
        }
        return render_template("pages/event.j2", **ctx)

    def post(self, id: int) -> Response | str:
        event_obj = get_public_obj(id, EventPost)
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
            case "request-accreditation":
                response = self._request_accreditation(user, event_obj)
                db.session.commit()
                return response
            case "withdraw-accreditation":
                response = self._withdraw_accreditation(user, event_obj)
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

    def _request_accreditation(self, user: User, event_obj: EventPost) -> Response:
        """Demander une accréditation (RG-03).

        Remplace l'ancienne bascule, qui accréditait d'un clic. Le
        membre demande désormais, et l'organisateur décide depuis son
        écran « Accréditer ».

        `403` hors audience, `409` sur un événement clos — avec un
        message en clair, comme le faisait le refus par rôle.

        Note: does NOT commit — caller is responsible.
        """
        try:
            request_accreditation(event_obj, user)
        except PermissionError as e:
            return make_response(str(e), 403)
        except AccreditationClosedError as e:
            return make_response(str(e), 409)

        return self._accreditation_fragment(
            event_obj, user, f"Votre demande pour {event_obj.title!r} a été envoyée"
        )

    def _withdraw_accreditation(self, user: User, event_obj: EventPost) -> Response:
        """Annuler sa demande, ou se désinscrire (RG-08).

        Les deux gestes sont le même côté membre.

        `409` sur un événement annulé (ANN-05) : le geste n'a plus de
        sens, et la ligne existante est conservée — c'est elle qui dit
        à qui l'on doit un message si l'événement est rétabli.

        Note: does NOT commit — caller is responsible.
        """
        try:
            withdraw_accreditation(event_obj, user)
        except AccreditationClosedError as e:
            return make_response(str(e), 409)

        return self._accreditation_fragment(
            event_obj, user, f"Vous êtes retiré de l'événement {event_obj.title!r}"
        )

    def _accreditation_fragment(
        self, event_obj: EventPost, user: User, toast: str
    ) -> Response:
        """Le bloc de statut, re-rendu pour HTMX, plus le toast."""
        db.session.flush()
        html = render_template(
            "pages/event--accreditation.j2",
            event=event_obj,
            accreditation=_accreditation_status(event_obj, user),
            is_open=is_open(event_obj),
            sees_content=True,
        )
        response = make_response(html)
        response.headers["HX-Trigger"] = json.dumps({"showToast": toast})
        return response

    def _post_comment(self, event_obj: EventPost) -> Response:
        """Post a comment on the event.

        Note: Does NOT commit - caller is responsible for committing.
        """
        if event_obj.cancelled_at is not None:
            # ANN-05 — un événement annulé ne se commente plus. Les
            # commentaires déjà postés restent, eux : ils font partie de
            # l'histoire publique de l'annonce.
            return make_response("Cet événement a été annulé.", 409)

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
            # MOD-01 : le format est public. `access_details` ne l'est
            # pas et n'a rien à faire ici — cette liste est rendue par
            # `event--aside.j2`, que rien ne garde.
            {"label": "Format", "value": MODE_LABELS[item.mode], "href": "events"},
            # PRX-04 — public, et fonction du lecteur : c'est
            # l'information qu'on cherche avant de se déplacer.
            # `getattr` et non `g.user` : un visiteur anonyme est un
            # lecteur que la règle prévoit — il lit la colonne « autre
            # membre », c'est-à-dire ce qu'il paierait.
            {"label": "Tarif", "value": price_label(item, getattr(g, "user", None))},
        ]
        # ORG-03 — seulement quand un organisateur a été désigné : à
        # vide, la cascade retombe sur l'éditeur, et une ligne
        # « Organisateur : <l'éditeur> » n'apprendrait rien.
        if item.has_explicit_organiser:
            data.append({"label": "Organisateur", "value": item.organiser_label})
        if item.platform:
            data.append({"label": "Plateforme", "value": item.platform})

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
