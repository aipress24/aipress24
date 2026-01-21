# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, cast

from flask import Flask, Response, flash, redirect, render_template, request
from flask_classful import route
from flask_login import current_user
from flask_super.registry import register
from svcs.flask import container
from werkzeug.wrappers import Response as WerkzeugResponse

from app.flask.lib.htmx import extract_fragment
from app.flask.routing import url_for
from app.models.lifecycle import PublicationStatus

# from app.logging import warn
from app.modules.wip.models import (
    AvisEnquete,
    AvisEnqueteRepository,
    RDVStatus,
    RDVType,
    StatutAvis,
)
from app.modules.wip.services.newsroom import (
    AvisEnqueteService,
    ExpertFilterService,
    RDVAcceptanceData,
    RDVProposalData,
)
from app.services.auth import AuthService

from ._base import BaseWipView
from ._forms import AvisEnqueteForm
from ._table import BaseTable

if TYPE_CHECKING:
    from app.models.auth import User


class AvisEnqueteTable(BaseTable):
    id = "avis-enquete-table"

    def __init__(self, q="") -> None:
        super().__init__(AvisEnquete, q)

    def url_for(self, obj, _action="get", **kwargs):  # type: ignore[override]
        return url_for(f"AvisEnqueteWipView:{_action}", id=obj.id, **kwargs)

    def get_actions(self, item):
        return [
            {
                "label": "Voir",
                "url": self.url_for(item),
            },
            {
                "label": "Modifier",
                "url": self.url_for(item, "edit"),
            },
            {
                "label": "Cibler les contacts",
                "url": self.url_for(item, "ciblage"),
            },
            {
                "label": "Gérer les réponses",
                "url": self.url_for(item, "reponses"),
            },
            {
                "label": "Gérer les RDV",
                "url": self.url_for(item, "rdv"),
            },
            {
                "label": "Supprimer",
                "url": self.url_for(item, "delete"),
            },
        ]


class AvisEnqueteWipView(BaseWipView):
    name = "avis_enquete"

    model_class = AvisEnquete
    repo_class = AvisEnqueteRepository
    table_class = AvisEnqueteTable
    doc_type = "avis_enquete"
    form_class = AvisEnqueteForm

    route_base = "avis-enquete"
    path = "/wip/avis-enquete/"

    # UI
    icon = "newspaper"

    label_main = "Newsroom: Avis d'enquête"
    label_list = "Liste des avis d'enquête"
    label_new = "Créer un avis d'enquête"
    label_edit = "Modifier l'avis d'enquête"
    label_view = "Voir l'avis d'enquête"

    table_id = "avis-enquete-table-body"

    msg_delete_ok = "L'avis d'enquête a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer cet avis d'enquête"

    @route("/<id>/ciblage", methods=["GET", "POST"])
    def ciblage(self, id: str | int):
        model: AvisEnquete = self._get_model(id)
        title = f"Ciblage des contacts - {model.title}"
        self.update_breadcrumbs(label=model.title)
        # Use services
        filter_service = ExpertFilterService()
        filter_service.initialize(avis_enquete_id=str(id))
        filter_service.save_state()
        filter_service._selectors = None

        avis_service = AvisEnqueteService()
        action = filter_service.get_action_from_request()

        match action:
            case "confirm":
                selected_experts = filter_service.get_selected_experts()
                new_experts = avis_service.filter_known_experts(model, selected_experts)
                nb_new_experts = len(new_experts)
                if nb_new_experts > 0:
                    model.status = PublicationStatus.PUBLIC
                    sender = cast("User", current_user)
                    avis_service.store_contacts(model, new_experts)
                    avis_service.notify_experts(model, new_experts, "#TODO")
                    avis_service.send_avis_enquete_emails(model, new_experts, sender)
                    avis_service.commit()
                    if nb_new_experts > 1:
                        msg = f"Avis d'enquête envoyé aux {len(new_experts)} contacts sélectionnés"
                    else:
                        msg = "Avis d'enquête envoyé au contact sélectionné"
                    flash(msg, "success")
                else:
                    flash("Aucun nouvel expert sélectionné", "error")
                response = Response("")
                response.headers["HX-Redirect"] = url_for("AvisEnqueteWipView:index")
                return response
            case "update":
                filter_service.update_experts_from_request()
                filter_service.save_state()
            case "add":
                filter_service.add_experts_from_request()
                filter_service.save_state()
            case "":
                pass
            case _:
                msg = f"Invalid action: {action}"
                raise ValueError(msg)

        experts = filter_service.get_selectable_experts()
        selected_experts = filter_service.get_selected_experts()

        ctx = {
            "form": filter_service,  # Template uses form.selectors
            "experts": experts,
            "selected_experts": selected_experts,
            "title": title,
            "model": model,
        }

        html = render_template("wip/avis_enquete/ciblage.j2", **ctx)
        html = extract_fragment(html, "main")
        filter_service.save_state()
        return html

    @route("/<id>/reponses", methods=["GET"])
    def reponses(self, id):
        model = self._get_model(id)
        title = f"Gestion des réponses - {model.title}"
        self.update_breadcrumbs(label=title)

        service = AvisEnqueteService()
        responses = service.get_contacts_for_avis(model.id)

        ctx = {
            "title": title,
            "model": model,
            "responses": responses,
            "StatutAvis": StatutAvis,
            "RDVStatus": RDVStatus,
        }

        html = render_template("wip/avis_enquete/reponses.j2", **ctx)
        return html

    @route("/<id>/rdv", methods=["GET"])
    def rdv(self, id):
        model = self._get_model(id)
        title = f"Gestion des rendez-vous - {model.title}"
        self.update_breadcrumbs(label=title)

        service = AvisEnqueteService()
        contacts_with_rdv = service.get_contacts_with_rdv(model.id)

        ctx = {
            "title": title,
            "model": model,
            "contacts_with_rdv": contacts_with_rdv,
        }

        html = render_template("wip/avis_enquete/rdv.j2", **ctx)
        return html

    @route("/<id>/rdv-details/<contact_id>", methods=["GET"])
    def rdv_details(self, id, contact_id):
        model = self._get_model(id)
        service = AvisEnqueteService()

        contact = service.get_contact_for_avis(int(contact_id), model.id)
        if not contact:
            flash("Contact introuvable", "error")
            return self._htmx_redirect("rdv", id=id)

        title = f"Détails du RDV - {contact.expert.full_name}"
        self.update_breadcrumbs(label=title)

        ctx = {
            "title": title,
            "model": model,
            "contact": contact,
            "RDVStatus": RDVStatus,
        }

        html = render_template("wip/avis_enquete/rdv_details.j2", **ctx)
        return html

    @route("/<id>/rdv-confirm/<contact_id>", methods=["POST"])
    def rdv_confirm(self, id, contact_id):
        model = self._get_model(id)
        service = AvisEnqueteService()

        contact = service.get_contact_for_avis(int(contact_id), model.id)
        if not contact:
            flash("Contact introuvable", "error")
            return self._htmx_redirect("rdv", id=id)

        # Verify current user is the journalist
        if current_user.id != contact.journaliste_id:
            flash("Vous n'êtes pas autorisé à confirmer ce RDV", "error")
            return self._htmx_redirect("rdv_details", id=id, contact_id=contact.id)

        if not contact.can_confirm_rdv():
            flash("Ce RDV ne peut pas être confirmé", "error")
            return self._htmx_redirect("rdv_details", id=id, contact_id=contact.id)

        try:
            contact.confirm_rdv()
            service.send_rdv_confirmed_email(contact)
            service.commit()
            flash("Le RDV a été confirmé", "success")
        except ValueError as e:
            flash(str(e), "error")

        return self._htmx_redirect("reponses", id=id)

    @route("/<id>/rdv-cancel/<contact_id>", methods=["POST"])
    def rdv_cancel(self, id, contact_id):
        model = self._get_model(id)
        service = AvisEnqueteService()

        contact = service.get_contact_for_avis(int(contact_id), model.id)
        if not contact:
            flash("Contact introuvable", "error")
            return self._htmx_redirect("rdv", id=id)

        # Verify we are the journalist or the expert
        user_is_journalist = current_user.id == contact.journaliste_id
        user_is_expert = current_user.id == contact.expert_id

        if not (user_is_journalist or user_is_expert):
            flash("Vous n'êtes pas autorisé à annuler ce RDV", "error")
            return self._htmx_redirect("rdv_details", id=id, contact_id=contact.id)

        if not contact.can_cancel_rdv():
            flash("Ce RDV ne peut pas être annulé", "error")
            return self._htmx_redirect("rdv_details", id=id, contact_id=contact.id)

        try:
            service.cancel_rdv(contact.id)
            if user_is_journalist:
                service.send_rdv_cancelled_by_journalist_email(contact)
            else:
                service.send_rdv_cancelled_by_expert_email(contact)
            service.commit()
            flash("Le RDV a été annulé", "success")
        except ValueError as e:
            flash(str(e), "error")

        return self._htmx_redirect("reponses", id=id)

    @route("/<id>/rdv-propose/<contact_id>", methods=["GET", "POST"])
    def rdv_propose(self, id, contact_id):
        model = self._get_model(id)
        service = AvisEnqueteService()

        contact = service.get_contact_for_avis(int(contact_id), model.id)
        if not contact:
            flash("Contact introuvable", "error")
            return self._htmx_redirect("reponses", id=id)

        if request.method == "POST":
            # Parse form data
            try:
                data = self._parse_rdv_proposal_form()
            except ValueError as e:
                flash(str(e), "error")
                return self._htmx_redirect("rdv_propose", id=id, contact_id=contact_id)

            # Use service to propose RDV
            try:
                notification_url = url_for(
                    "AvisEnqueteWipView:rdv_accept",
                    id=model.id,
                    contact_id=contact.id,
                )
                service.propose_rdv(int(contact_id), data, notification_url)
                service.notify_rdv_proposed(contact, notification_url)
                service.send_rdv_proposed_email(contact)
                service.commit()
            except ValueError as e:
                flash(str(e), "error")
                return self._htmx_redirect("rdv_propose", id=id, contact_id=contact_id)

            flash("Votre proposition de rendez-vous a été envoyée", "success")
            return self._htmx_redirect("reponses", id=id)

        title = f"Proposer un RDV - {contact.expert.full_name}"
        self.update_breadcrumbs(label=title)

        ctx = {
            "title": title,
            "model": model,
            "contact": contact,
        }

        html = render_template("wip/avis_enquete/rdv_propose.j2", **ctx)
        return html

    def _parse_rdv_proposal_form(self) -> RDVProposalData:
        """Parse and validate form data into RDVProposalData."""
        rdv_type = RDVType[request.form.get("rdv_type", "")]

        proposed_slots = []
        for i in range(1, 6):  # Support up to 5 slots
            slot_str = request.form.get(f"slot_datetime_{i}")
            if slot_str:
                try:
                    slot_dt = datetime.fromisoformat(slot_str)
                    proposed_slots.append(slot_dt)
                except ValueError as err:
                    msg = f"Format de date/heure invalide pour le créneau {i}"
                    raise ValueError(msg) from err

        return RDVProposalData(
            rdv_type=rdv_type,
            proposed_slots=proposed_slots,
            rdv_phone=request.form.get("rdv_phone", ""),
            rdv_video_link=request.form.get("rdv_video_link", ""),
            rdv_address=request.form.get("rdv_address", ""),
            rdv_notes=request.form.get("rdv_notes", ""),
        )

    @route("/<id>/rdv-accept/<contact_id>", methods=["GET", "POST"])
    def rdv_accept(self, id, contact_id):
        """Expert view to accept a proposed RDV slot."""
        model = self._get_model(id)
        service = AvisEnqueteService()

        contact = service.get_contact_for_avis(int(contact_id), model.id)
        if not contact:
            flash("Contact introuvable", "error")
            return self._htmx_redirect_url(url_for("public.home"))

        # RDV already done
        if request.method == "GET" and not contact.can_accept_rdv():
            flash(
                "Ce RDV a déjà été traité ou n'est plus en attente de réponse.", "info"
            )
            return redirect(
                url_for(
                    "AvisEnqueteWipView:rdv_details",
                    id=model.id,
                    contact_id=contact.id,
                )
            )

        # Verify that the current user is the expert
        auth_service = container.get(AuthService)
        current = auth_service.get_user()
        if current.id != contact.expert_id:
            flash("Vous n'êtes pas autorisé à accéder à cette page", "error")
            return self._htmx_redirect_url(url_for("public.home"))

        if request.method == "POST":
            action = request.form.get("action")
            match action:
                case "refuse":
                    try:
                        notification_url = url_for(
                            "AvisEnqueteWipView:reponses", id=model.id
                        )
                        service.refuse_rdv(int(contact_id), notification_url)
                        service.notify_rdv_refused(contact, notification_url)
                        # TODO=
                        # service.send_rdv_refused_email(contact)
                        service.commit()
                    except ValueError as e:
                        flash(str(e), "error")
                        return self._htmx_redirect(
                            "rdv_accept", id=id, contact_id=contact_id
                        )

                    flash(
                        "Vous avez refusé le rendez-vous.",
                        "success",
                    )
                    return self._htmx_redirect_url(url_for("wip.opportunities"))

                case "accept":
                    try:
                        data: RDVAcceptanceData | None = (
                            self._parse_rdv_acceptance_form()
                        )
                    except ValueError as e:
                        flash(str(e), "error")
                        return self._htmx_redirect(
                            "rdv_accept", id=id, contact_id=contact_id
                        )

                    if data is None:
                        try:
                            notification_url = url_for(
                                "AvisEnqueteWipView:reponses", id=model.id
                            )
                            service.refuse_rdv(int(contact_id), notification_url)
                            service.notify_rdv_refused(contact, notification_url)
                            # TODO=
                            # service.send_rdv_refused_email(contact)
                            service.commit()
                        except ValueError as e:
                            flash(str(e), "error")
                            return self._htmx_redirect(
                                "rdv_accept", id=id, contact_id=contact_id
                            )

                        flash(
                            "Vous avez refusé le rendez-vous.",
                            "success",
                        )
                        return self._htmx_redirect_url(url_for("wip.opportunities"))

                    # Use service to accept RDV
                    try:
                        notification_url = url_for(
                            "AvisEnqueteWipView:reponses", id=model.id
                        )
                        service.accept_rdv(int(contact_id), data, notification_url)
                        service.notify_rdv_accepted(contact, notification_url)
                        service.send_rdv_accepted_email(contact)
                        service.commit()
                    except ValueError as e:
                        flash(str(e), "error")
                        return self._htmx_redirect(
                            "rdv_accept", id=id, contact_id=contact_id
                        )

                    flash(
                        "Vous avez accepté le rendez-vous. Le journaliste sera notifié.",
                        "success",
                    )
                    return self._htmx_redirect_url(url_for("wip.opportunities"))

        title = f"Accepter un rendez-vous - {model.title}"
        self.update_breadcrumbs(label=title)

        ctx = {
            "title": title,
            "model": model,
            "contact": contact,
        }

        html = render_template("wip/avis_enquete/rdv_accept.j2", **ctx)
        return html

    def _parse_rdv_acceptance_form(self) -> RDVAcceptanceData | None:
        """Parse and validate form data into RDVAcceptanceData."""
        selected_slot_str = request.form.get("selected_slot")
        if not selected_slot_str:
            msg = "Aucun créneau sélectionné"
            raise ValueError(msg)

        if selected_slot_str == "decline":
            return None

        try:
            selected_slot = datetime.fromisoformat(selected_slot_str)
        except ValueError as err:
            msg = "Format de créneau invalide"
            raise ValueError(msg) from err

        return RDVAcceptanceData(
            selected_slot=selected_slot,
            expert_notes=request.form.get("expert_notes", ""),
        )

    def _htmx_redirect(self, action: str, **kwargs) -> Response | WerkzeugResponse:
        """HTMX-aware redirect to a view action."""
        redirect_url = url_for(f"AvisEnqueteWipView:{action}", **kwargs)
        return self._htmx_redirect_url(redirect_url)

    def _htmx_redirect_url(self, redirect_url: str) -> Response | WerkzeugResponse:
        """HTMX-aware redirect to a URL."""
        if request.headers.get("HX-Request"):
            return Response("", headers={"HX-Redirect": redirect_url})
        return redirect(redirect_url)


@register
def register_on_app(app: Flask) -> None:
    AvisEnqueteWipView.register(app)
