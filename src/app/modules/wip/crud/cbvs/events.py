# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import arrow
import sqlalchemy as sa
from flask import (
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
)
from flask_classful import route
from flask_super.registry import register
from sqlalchemy.orm import Session
from werkzeug.exceptions import Forbidden, NotFound
from werkzeug.wrappers import Response

from app.enums import CommunityEnum
from app.flask.extensions import db
from app.flask.lib.templates import templated
from app.flask.routing import url_for
from app.lib.file_object_utils import create_file_object
from app.lib.image_utils import extract_image_from_request
from app.logging import report_failure, warn
from app.models.lifecycle import PublicationStatus
from app.modules.bw.bw_activation.models import PermissionType
from app.modules.bw.bw_activation.user_utils import (
    can_user_publish_for,
    get_selected_business_wall_for_user,
)
from app.modules.events.notifications import (
    EventStatusChange,
    notify_status_change,
)
from app.modules.events.review import is_reviewer
from app.modules.wip.models.eventroom import (
    Event,
    EventImage,
    EventImageRepository,
    EventRepository,
)
from app.modules.wip.pr_access import (
    user_can_access_eventroom,
    user_has_mission,
    user_is_acting_as_pr_manager,
)
from app.modules.wip.services.pr_notifications import (
    absolute_url_for,
    notify_client_of_pr_publication,
)
from app.settings.constants import MAX_IMAGE_SIZE
from app.signals import (
    event_published,
    event_unpublished,
    event_updated,
)

from ._base import BaseWipView
from ._forms import EventForm
from ._table import BaseTable

if TYPE_CHECKING:
    from app.lib.image_utils import UploadedImageData


class EventsTable(BaseTable):
    id = "events-table"

    def __init__(self, q="") -> None:
        super().__init__(Event, q)

    def url_for(self, obj, _action="get", **kwargs):
        return url_for(f"EventsWipView:{_action}", id=obj.id, **kwargs)

    def get_actions(self, item):
        actions = [
            {
                "label": "Draft",
                "url": self.url_for(item),
            },
            {
                "label": "Modifier",
                "url": self.url_for(item, "edit"),
            },
            {
                "label": "Images",
                "url": self.url_for(item, "images"),
            },
            {
                "label": "Cibler",
                "url": self.url_for(item, "audience"),
            },
            {
                "label": _accrediter_label(item),
                "url": self.url_for(item, "accreditations"),
            },
        ]
        actions += _publication_actions(item, self.url_for)
        # ANN-01 — annuler et rétablir mènent au même écran : c'est la
        # même décision, prise dans un sens ou dans l'autre. Ni l'une ni
        # l'autre n'est proposée sur un brouillon, qui n'a été annoncé
        # à personne.
        if item.can_cancel():
            actions.append(
                {
                    "label": "Annuler l'événement",
                    "url": self.url_for(item, "cancel"),
                }
            )
        elif item.can_restore():
            actions.append(
                {
                    "label": "Rétablir l'événement",
                    "url": self.url_for(item, "cancel"),
                }
            )
        actions += [
            {
                "label": "Supprimer",
                "url": self.url_for(item, "delete"),
            },
        ]
        return actions


# Ticket #0154: surface the step-nav bar on the Voir / Modifier pages
# (carried over from #0151 on Avis d'enquête). See the corresponding
# block in articles.py for rationale.
# language=jinja2
_EVENT_VOIR_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% from "wip/_step_nav_simple.j2" import step_nav_simple %}
{% block body_content %}
  {{ step_nav_simple(event, "EventsWipView", "voir", "événements") }}
  {{ form_rendered|safe }}
  {{ extra_view_html|safe }}
  {{ step_nav_simple(event, "EventsWipView", "voir", "événements") }}
{% endblock %}
"""

# language=jinja2
_EVENT_MODIFIER_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% from "wip/_step_nav_simple.j2" import step_nav_simple %}
{% block body_content %}
  {{ step_nav_simple(event, "EventsWipView", "modifier", "événements") }}
  {{ form_rendered|safe }}
  {{ step_nav_simple(event, "EventsWipView", "modifier", "événements") }}
{% endblock %}
"""


def _publication_actions(item, url_for) -> list[dict]:
    """Ce que l'utilisateur peut faire avancer sur cet événement (REL-02).

    Quatre transitions et deux acteurs, d'où une fonction plutôt qu'une
    cascade dans `get_actions` : la règle est un tableau dans la
    spécification.

    À `event_review_required == False` — le défaut, et l'état de toutes
    les organisations existantes — ce bloc rend exactement ce qu'il
    rendait avant le lot : « Publier » sur un brouillon, « Dépublier »
    sinon. C'est ce que REL-03 exige.
    """
    from app.modules.events.review import is_reviewer, review_required

    # `getattr` : ce tableau est aussi construit hors d'une requête
    # authentifiée — dans les tests unitaires du menu, notamment. Sans
    # lecteur, il n'y a pas de relecteur, et le parcours par défaut
    # s'applique.
    user = getattr(g, "user", None)
    if item.status == PublicationStatus.PUBLIC:
        return [{"label": "Dépublier", "url": url_for(item, "unpublish")}]

    reviews = review_required(item.publisher)
    reviewer = is_reviewer(user, item.publisher) if reviews else False

    if item.status == PublicationStatus.PENDING:
        # Seul un relecteur décide d'un événement en relecture. L'auteur
        # qui l'a soumis n'a plus la main : c'est tout l'objet du
        # circuit.
        if not reviewer:
            return []
        return [
            {"label": "Valider et publier", "url": url_for(item, "publish")},
            {"label": "Renvoyer à l'auteur", "url": url_for(item, "review")},
        ]

    # DRAFT
    if reviews and not reviewer:
        return [{"label": "Soumettre à relecture", "url": url_for(item, "review")}]
    return [{"label": "Publier", "url": url_for(item, "publish")}]


def _accrediter_label(event) -> str:
    """« Accréditer (3) » — le compteur porte les demandes en attente.

    Sans lui, rien ne signale à l'organisateur qu'on attend une
    décision de sa part : la cloche n'arrive qu'au lot C1.
    """
    pending = _pending_count(event)
    return f"Accréditer ({pending})" if pending else "Accréditer"


def _require_organiser(event) -> None:
    """Refuser l'accès à qui n'organise pas cet événement (§6).

    `before_request` garde l'accès à Event'Room dans son ensemble, mais
    pas événement par événement : n'importe quel membre y ayant accès
    atteignait les écrans de n'importe quel autre. C'est sans grande
    conséquence sur un formulaire de saisie ; ça n'en a plus dès que
    l'écran liste des profils nominatifs — nom, photo, fonction,
    organisation — ou permet de changer qui est invité.

    Sont autorisés le propriétaire, et **les rôles habilités** du
    Business Wall de l'organisation éditrice. Pas la simple
    appartenance à cette organisation : dans un média de deux cents
    journalistes, elle ouvrirait la liste nominative des demandeurs de
    n'importe quel événement de la maison à tout le monde — ce que
    `can_user_publish_for` faisait, sa première condition étant
    l'appartenance.
    """
    user = g.user
    if event.owner_id == user.id:
        return
    if event.publisher and _has_events_mission_on(user, event.publisher):
        return
    raise Forbidden


def _has_events_mission_on(user, organisation) -> bool:
    """L'utilisateur porte-t-il la mission « événements » sur le BW de
    cette organisation ?

    Vrai pour le propriétaire du Business Wall, et pour toute
    attribution de rôle acceptée qui accorde explicitement cette
    permission.
    """
    from app.modules.bw.bw_activation.user_utils import (
        get_active_business_wall_for_organisation,
    )
    from app.modules.wip.pr_access import _bw_grants_mission

    bw = get_active_business_wall_for_organisation(organisation)
    if bw is None:
        return False
    return _bw_grants_mission(bw, user.id, PermissionType.EVENTS)


def _event_post_of(event):
    """Le `EventPost` public correspondant, s'il est publié.

    Les accréditations pendent du post public, pas de l'événement de
    saisie : tant qu'il n'est pas publié, il n'y a personne à
    accréditer.
    """
    from app.modules.events.models import EventPost

    return db.session.scalars(
        sa.select(EventPost).where(EventPost.eventroom_id == event.id)
    ).one_or_none()


def _pending_count(event) -> int:
    """Nombre de demandes en attente de décision."""
    return _count_accreditations(event, "REQUESTED")


def _count_accreditations(event, status_name: str) -> int:
    """Compter les accréditations d'un événement dans un statut donné.

    Deux appelants : le compteur du menu (demandes en attente) et
    l'écran de ciblage (déjà accrédités), qui rappelle qu'un changement
    d'audience ne déaccrédite personne.
    """
    from app.modules.events.models import Accreditation, AccreditationStatus

    post = _event_post_of(event)
    if post is None:
        return 0
    stmt = sa.select(sa.func.count()).where(
        Accreditation.event_id == post.id,
        Accreditation.status == AccreditationStatus[status_name],
    )
    return db.session.execute(stmt).scalar() or 0


def _accredited_count(event) -> int:
    return _count_accreditations(event, "ACCEPTED")


class EventsWipView(BaseWipView):
    name = "events"

    model_class = Event
    repo_class = EventRepository
    table_class = EventsTable
    form_class = EventForm
    doc_type = "event"

    route_base = "events"
    path = "/wip/events/"

    # UI
    icon = "calendar"

    label_main = "Evénements"
    label_list = "Liste des événements"
    label_new = "Créer un événement"
    label_edit = "Modifier l'événement"
    label_view = "Voir de draft de l'événement"

    table_id = "events-table-body"

    msg_delete_ok = "L'événement a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer cet événement"

    def before_request(self, *_args, **_kwargs) -> Response | None:
        if resp := super().before_request(*_args, **_kwargs):
            return resp

        user = g.user
        if not user_can_access_eventroom(user):
            raise Forbidden

        if user_is_acting_as_pr_manager(user) and not user_has_mission(
            user, PermissionType.EVENTS
        ):
            raise Forbidden

        return None

    @templated(_EVENT_VOIR_TEMPLATE)
    def get(self, id):
        """Step « Voir » — wrapped with the #0154 step-nav bar."""
        model = self._get_model(id)
        title = f"{self.label_view} '{model.title}'"
        ctx = self._view_ctx(model, title=title, mode="view")
        ctx["event"] = model
        return ctx

    @templated(_EVENT_MODIFIER_TEMPLATE)
    def edit(self, id):
        """Step « Modifier » — wrapped with the #0154 step-nav bar."""
        model = self._get_model(id)
        title = f"{self.label_edit} '{model.title}'"
        ctx = self._view_ctx(model, title=title)
        ctx["event"] = model
        return ctx

    def _post_update_model(self, model: Event) -> None:
        # Validate publisher_id: if the user selected a client org they are
        # not auth to publish for, warn but DO NOT silently reset — the
        # publish() step will enforce the auth and show an explicit error.
        if model.publisher_id and not can_user_publish_for(g.user, model.publisher_id):
            warn(
                f"Event {model.id}: user {g.user.id} selected publisher_id="
                f"{model.publisher_id} but can_user_publish_for is False. "
                "Keeping the value so the user sees the error at publish time."
            )
        if not model.publisher_id:
            if g.user.is_managing_another_bw:
                bw = get_selected_business_wall_for_user(g.user)
                if bw:
                    model.publisher_id = bw.organisation_id
            if not model.publisher_id and g.user.organisation_id:
                model.publisher_id = g.user.organisation_id

        if not model.status:
            model.status = PublicationStatus.DRAFT  # type: ignore[assignment]
            model.published_at = arrow.now("Europe/Paris")

        # MOD-01, PRX-02, REL-04 — les règles gouvernent l'**état
        # publié**, pas l'instant de la publication. Sans cette
        # relecture, un organisateur publiait un événement valide puis
        # le modifiait vers un état que la publication aurait refusé —
        # un présentiel sans adresse, un tarif payant sans prix — et cet
        # état partait sur la carte, où il s'affichait en tiret nu.
        #
        # `PENDING` en fait partie : un auteur peut encore éditer son
        # événement pendant qu'il attend une relecture, et REL-04 dit
        # qu'un relecteur ne doit jamais hériter d'un brouillon
        # impubliable — pas seulement au moment de la soumission.
        #
        # Un brouillon reste librement incomplet : c'est ce qu'est un
        # brouillon.
        if model.status in (PublicationStatus.PUBLIC, PublicationStatus.PENDING):
            model.check_publishable()

        event_updated.send(model)

    def publish(self, id):
        repo = self._get_repo()
        event = cast("Event", self._get_model(id))

        publisher_id = event.publisher_id or g.user.organisation_id or None
        if publisher_id and not can_user_publish_for(g.user, publisher_id):
            flash(
                "Vous n'êtes pas autorisé à publier pour cette organisation.",
                "error",
            )
            return redirect(self._url_for("edit", id=id))

        # REL-02 — « Valider et publier » n'appartient qu'à un relecteur.
        # `can_user_publish_for` ne suffit pas : sa première condition
        # est l'appartenance à l'organisation, si bien que n'importe quel
        # collègue de l'auteur pourrait valider sa propre soumission —
        # et le circuit de relecture ne vaudrait plus rien.
        if event.status == PublicationStatus.PENDING and not is_reviewer(
            g.user, event.publisher
        ):
            flash(
                "Seul un relecteur de l'organisation peut valider cet événement.",
                "error",
            )
            return redirect(self._url_for("index"))

        try:
            event.publish(publisher_id=publisher_id)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("edit", id=id))

        repo.update(event, auto_commit=False)
        event_published.send(event)
        db.session.commit()

        if (
            event.publisher
            and g.user.organisation_id
            and event.publisher_id != g.user.organisation_id
        ):
            try:
                notify_client_of_pr_publication(
                    author=g.user,
                    client_org=event.publisher,
                    content_type="événement",
                    content_title=event.titre,
                    content_url=absolute_url_for("EventsWipView:get", id=event.id),
                )
            except Exception as exc:
                report_failure(f"PR publication notif failed (event {event.id})", exc)

        flash("L'événement a été publié")
        return redirect(self._url_for("index"))

    def unpublish(self, id):
        repo = self._get_repo()
        event = cast("Event", self._get_model(id))

        # Use business method to unpublish (includes validation)
        try:
            event.unpublish()
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("get", id=id))

        repo.update(event, auto_commit=False)
        event_unpublished.send(event)
        db.session.commit()
        # NOT-05, troisième déclencheur : retirer l'annonce prive les
        # accrédités de la page qui les renseignait. Après le commit,
        # jamais avant.
        self._notify_accredited(event, EventStatusChange.UNPUBLISHED)
        flash("L'événement a été dépublié")
        return redirect(self._url_for("index"))

    def _post_delete_model(self, model) -> None:
        # Deleting a published source must take its public event mirror down too:
        # re-emit the unpublish signal so the mirror flips to DRAFT and is
        # de-indexed. The receiver no-ops if the source was never published.
        #
        # Pas de NOT-05 ici, délibérément : la suppression passe par ce
        # signal et non par la route `unpublish`, et prévenir des gens
        # d'un retrait en les renvoyant vers une page qui n'existe plus
        # ne les aide pas. L'organisateur qui veut les prévenir annule,
        # ce qui est justement le geste que ce lot lui donne.
        event_unpublished.send(model)

    @route("/to-review/", methods=["GET"])
    def to_review(self):
        """L'écran « À relire » (REL-06).

        Sa propre requête, parce que la liste ordinaire de l'atelier est
        filtrée par propriétaire : un relecteur n'y verrait jamais
        l'événement d'un collègue, et c'est précisément ce qu'il doit
        voir.

        Le chemin est déclaré explicitement : `flask-classful` expose
        toute méthode publique comme une route, et une méthode nommée
        `to_review` donnerait `/wip/events/to_review/` — souligné
        compris.
        """
        from app.modules.events.review import events_to_review
        from app.modules.wip.views._common import get_secondary_menu

        events = events_to_review(g.user)
        return render_template(
            "wip/event/to_review.j2",
            title="Événements à relire",
            events=events,
            menus={"secondary": get_secondary_menu("eventroom")},
        )

    @route("/<int:id>/review/", methods=["GET", "POST"])
    def review(self, id: int):
        """Soumettre à relecture, ou renvoyer à l'auteur (REL-02).

        Une seule route pour les deux gestes : ce sont les deux sens du
        même passage, et l'écran diffère par une phrase et un champ.

        L'habilitation n'est **pas** `_require_organiser` : soumettre
        est le geste de l'auteur, qui par construction n'est pas
        habilité — sinon il publierait directement. Chaque geste porte
        donc sa propre garde.
        """
        from app.modules.events.review import is_reviewer, review_required

        event = cast("Event", self._get_model(id))
        reviewer = is_reviewer(g.user, event.publisher)
        author = event.owner_id == g.user.id

        if not (reviewer or author):
            raise Forbidden

        if request.method == "POST":
            return self._apply_review(event, reviewer=reviewer, author=author)

        self.update_phase_breadcrumbs(event, "Relecture")
        return render_template(
            "wip/event/review.j2",
            title=f"Relecture — {event.title}",
            event=event,
            can_submit=author and event.can_submit_for_review(),
            can_send_back=reviewer and event.can_send_back(),
            reviews=review_required(event.publisher),
        )

    def _apply_review(self, event: Event, *, reviewer: bool, author: bool):
        """Appliquer la décision, puis prévenir qui de droit.

        Les notifications partent **après** le commit : un message est
        irréversible et ne doit jamais précéder l'écriture qui le
        justifie.
        """
        from app.modules.events.notifications import (
            notify_sent_back,
            notify_submitted_for_review,
        )
        from app.modules.events.review import reviewers_of

        action = request.form.get("_action", "")
        if action not in ("submit-for-review", "send-back"):
            raise NotFound
        if action == "submit-for-review" and not author:
            raise Forbidden
        if action == "send-back" and not reviewer:
            raise Forbidden

        comment = request.form.get("comment", "")
        try:
            if action == "submit-for-review":
                event.submit_for_review()
            else:
                event.send_back(comment)
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(self._url_for("review", id=event.id))

        db.session.commit()

        if action == "submit-for-review":
            count = notify_submitted_for_review(event, reviewers_of(event.publisher))
            db.session.commit()
            flash(
                f"Événement soumis à relecture. {count} relecteur(s) prévenu(s).",
                "success",
            )
        else:
            notify_sent_back(event, comment)
            db.session.commit()
            flash("Événement renvoyé à son auteur.", "success")

        return redirect(self._url_for("index"))

    @route("/<int:id>/cancel/", methods=["GET", "POST"])
    def cancel(self, id: int):
        """Annuler ou rétablir un événement (ANN-01, ANN-02, ANN-07).

        Une seule route pour les deux gestes, parce que c'est la même
        décision prise dans un sens ou dans l'autre, et que l'écran de
        confirmation est le même — il porte le nombre de personnes
        accréditées, qui est ce qui donne son poids au geste.
        """
        event = cast("Event", self._get_model(id))
        _require_organiser(event)

        if request.method == "POST":
            return self._apply_cancellation(event)

        self.update_phase_breadcrumbs(event, "Annuler")
        return render_template(
            "wip/event/cancel.j2",
            title=f"Annuler l'événement - {event.title}",
            event=event,
            accredited_count=_accredited_count(event),
            can_cancel=event.can_cancel(),
            can_restore=event.can_restore(),
            max_reason=Event.MAX_CANCELLATION_REASON,
        )

    def _apply_cancellation(self, event: Event):
        """Appliquer la décision, puis prévenir les accrédités.

        L'ordre compte : le miroir public porte le bandeau (ANN-04), et
        l'email de NOT-05 ne part qu'une fois le changement validé —
        un envoi est irréversible et ne doit jamais précéder l'écriture
        qui le justifie.
        """
        # « cancel-event » et non « cancel » : dans le vocabulaire de
        # formulaire de ce module, `_action="cancel"` veut déjà dire
        # « abandonner la saisie » (`_base.py`, et l'écran des images).
        # Le même mot pour deux gestes opposés se paie tôt ou tard.
        action = request.form.get("_action", "")
        if action not in ("cancel-event", "restore-event"):
            raise NotFound

        try:
            if action == "cancel-event":
                event.cancel(request.form.get("reason", ""))
            else:
                event.restore()
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(self._url_for("cancel", id=event.id))

        # Sans ce signal, annuler un événement **déjà publié** ne
        # changerait rien pour personne : c'est le miroir que lisent la
        # liste, le calendrier et le Business Wall.
        event_updated.send(event)
        db.session.commit()

        cancelling = action == "cancel-event"
        change = (
            EventStatusChange.CANCELLED if cancelling else EventStatusChange.RESTORED
        )
        notified = self._notify_accredited(event, change)
        done = "annulé" if cancelling else "rétabli"
        flash(
            f"L'événement a été {done}. {notified} personne(s) accréditée(s) "
            "ont été prévenues.",
            "success",
        )
        return redirect(self._url_for("index"))

    def _notify_accredited(self, event: Event, change: EventStatusChange) -> int:
        """NOT-05 vers les accrédités du miroir public, s'il existe.

        Les cloches sont des écritures : elles ont leur propre commit,
        après celui de la décision. S'il échouait, les cloches seraient
        perdues et les emails partis — le bon sens de la perte, la
        décision étant déjà acquise.
        """
        post = _event_post_of(event)
        if post is None:
            return 0
        notified = notify_status_change(post, change)
        db.session.commit()
        return notified

    @route("/<int:id>/audience/", methods=["GET", "POST"])
    def audience(self, id: int):
        """Restreindre l'audience d'un événement (RG-03a, écran §7.4).

        Aucune communauté cochée = ouvert à tous, ce qui est le défaut
        et le comportement des événements déjà publiés.

        Modifier le ciblage n'invalide **aucune** accréditation déjà
        accordée : on ne dépossède pas quelqu'un à qui l'on a dit oui.
        """
        event = cast("Event", self._get_model(id))
        _require_organiser(event)

        if request.method == "POST":
            event.audience = request.form.getlist("audience")
            # Le ciblage n'a d'effet qu'une fois recopié dans le miroir
            # public : c'est `EventPost.audience` que lisent toutes les
            # gardes. Sans ce signal, cibler un événement **déjà
            # publié** ne changerait rien pour personne.
            event_updated.send(event)
            db.session.commit()
            flash("Ciblage enregistré.", "success")
            return redirect(self._url_for("index"))

        self.update_phase_breadcrumbs(event, "Cibler")
        accredited = _accredited_count(event)
        return render_template(
            "wip/event/audience.j2",
            title=f"Cibler l'événement - {event.title}",
            event=event,
            communities=list(CommunityEnum),
            selected=set(event.audience or []),
            accredited_count=accredited,
        )

    @route("/<int:id>/accreditations/", methods=["GET", "POST"])
    def accreditations(self, id: int):
        """Décider des demandes d'accréditation (écran §7.5).

        Trois onglets — en cours, acceptées, rejetées — et des actions
        par lot. L'onglet des refus permet de revenir sur une décision
        (RG-13) ; c'est la seule sortie de `REJECTED`, et elle
        n'appartient qu'à l'organisateur.
        """
        from app.modules.events.models import AccreditationStatus
        from app.modules.events.services import (
            accept_accreditations,
            get_accreditations_by_status,
            reject_accreditations,
        )

        event = cast("Event", self._get_model(id))
        _require_organiser(event)
        post = _event_post_of(event)

        if request.method == "POST":
            if post is None:
                raise NotFound
            user_ids = [int(i) for i in request.form.getlist("user_ids")]
            decide = {
                "accept": accept_accreditations,
                "reject": reject_accreditations,
            }.get(request.form.get("_action", ""))
            if decide is None:
                raise NotFound
            count = decide(post, user_ids, decided_by=g.user)
            db.session.commit()
            flash(f"{count} demande(s) traitée(s).", "success")
            return redirect(self._url_for("accreditations", id=event.id))

        self.update_phase_breadcrumbs(event, "Accréditer")
        by_status = {
            status: get_accreditations_by_status(post, status) if post else []
            for status in (
                AccreditationStatus.REQUESTED,
                AccreditationStatus.ACCEPTED,
                AccreditationStatus.REJECTED,
            )
        }
        return render_template(
            "wip/event/accreditations.j2",
            title=f"Accréditer — {event.title}",
            event=event,
            published=post is not None,
            requested=by_status[AccreditationStatus.REQUESTED],
            accepted=by_status[AccreditationStatus.ACCEPTED],
            rejected=by_status[AccreditationStatus.REJECTED],
        )

    @route("/<int:id>/images/", methods=["GET", "POST"])
    def images(self, id: int):
        event = cast("Event", self._get_model(id))

        action = request.form.get("_action")
        match action:
            case "cancel":
                return redirect(self._url_for("index"))
            case "add-image":
                return self._add_image(event)

        title = f"Images pour l'événement - {event.title}"
        self.update_phase_breadcrumbs(event, "Images")

        ctx = {
            "title": title,
            "event": event,
        }

        html = render_template("wip/event/images.j2", **ctx)
        return html

    def _add_image(self, event: Event):
        event_repo = self._get_repo()
        image_repo = EventImageRepository(session=cast(Session, db.session))

        # Handle both regular file upload and base64 data URL from cropper
        result: UploadedImageData | None = extract_image_from_request(
            file_storage=request.files.get("image"),
            data_url=request.form.get("image"),
            orig_filename=request.form.get("image_filename") or None,
        )

        if result is None:
            flash("L'image est vide")
            return redirect(url_for("EventsWipView:images", id=event.id))

        image_bytes = result.bytes
        image_filename = result.filename
        image_content_type = result.content_type
        if len(image_bytes) >= MAX_IMAGE_SIZE:
            flash("L'image est trop volumineuse")
            return redirect(url_for("EventsWipView:images", id=event.id))
        caption = request.form.get("caption", "").strip()
        copyright = request.form.get("copyright", "").strip()

        image_file_object = create_file_object(
            content=image_bytes,
            original_filename=image_filename,
            content_type=image_content_type,
        )
        image_file_object.save()

        position = len(event.images)

        event_image = EventImage(
            caption=caption,
            copyright=copyright,
            content=image_file_object,
            owner=event.owner,
            event_id=event.id,
            position=position,
        )

        image_repo.add(event_image)
        # event.add_image(event_image)
        event_repo.update(event, auto_commit=False)
        db.session.commit()
        referrer_url = request.referrer or "/"
        redirect_url = referrer_url + "#last_image"
        return redirect(redirect_url)

    @route("/<int:event_id>/images/<int:image_id>")
    def image(self, event_id: int, image_id: int):
        event = cast("Event", self._get_model(event_id))
        image = next((im for im in event.images if im.id == image_id), None)
        if image is None:
            raise NotFound
        return redirect(image.url, code=301)

    @route("/<int:event_id>/images/<int:image_id>/delete", methods=["POST"])
    def delete_image(self, event_id: int, image_id: int):
        event = cast("Event", self._get_model(event_id))
        image = event.get_image(image_id)
        if not image:
            raise NotFound

        event.delete_image(image)
        if image.content:
            try:
                image.content.delete()
                warn(f"Success deleted file for Image {image_id}")
            except Exception as e:
                warn(f"Could not delete file {image_id}: {e}")

        db.session.delete(image)
        db.session.commit()

        return redirect(url_for("EventsWipView:images", id=event_id))

    @route("/<int:event_id>/images/<int:image_id>/move", methods=["POST"])
    def move_image(self, event_id: int, image_id: int):
        event = cast("Event", self._get_model(event_id))
        image = event.get_image(image_id)
        if not image:
            raise NotFound

        direction = request.form.get("direction")

        images = event.sorted_images
        assert [im.position for im in images] == list(range(len(images)))

        match direction:
            case "up":
                # pyrefly: ignore [bad-index]
                prev_image = images[image.position - 1]
                image.position -= 1
                prev_image.position += 1
            case "down":
                # pyrefly: ignore [bad-index]
                next_image = images[image.position + 1]
                image.position += 1
                next_image.position -= 1

        db.session.commit()

        return redirect(url_for("EventsWipView:images", id=event_id))


@register
def register_on_app(app: Flask) -> None:
    EventsWipView.register(app)
