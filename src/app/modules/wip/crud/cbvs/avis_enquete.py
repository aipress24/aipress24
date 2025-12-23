# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
import unicodedata
from abc import abstractmethod
from collections.abc import Generator
from typing import TYPE_CHECKING, cast

from attr import frozen
from flask import Flask, Response, flash, render_template, request
from flask_classful import route
from flask_login import current_user
from flask_super.registry import register
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.flask.lib.htmx import extract_fragment
from app.flask.routing import url_for
from app.logging import warn
from app.models.auth import User
from app.models.repositories import UserRepository
from app.modules.wip.models import (
    AvisEnquete,
    AvisEnqueteRepository,
    ContactAvisEnquete,
    ContactAvisEnqueteRepository,
)
from app.services.emails import AvisEnqueteNotificationMail
from app.services.notifications import NotificationService
from app.services.sessions import SessionService

# from app.services.taxonomies import get_full_taxonomy
from ._base import BaseWipView
from ._forms import AvisEnqueteForm
from ._table import BaseTable

if TYPE_CHECKING:
    from app.models.auth import User

MAX_SELECTABLE_EXPERTS = 50
MAX_OPTIONS = 100


class AvisEnqueteTable(BaseTable):
    id = "avis-enquete-table"

    def __init__(self, q="") -> None:
        super().__init__(AvisEnquete, q)

    def url_for(self, obj, _action="get", **kwargs):
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
    def ciblage(self, id):
        model: AvisEnquete = self._get_model(id)
        title = f"Ciblage des contacts - {model.title}"
        self.update_breadcrumbs(label=model.title)

        form = SearchForm()

        form.save_state()

        action = form.get_action()

        match action:
            case "confirm":
                selected_experts: list[User] = form.get_selected_experts()
                new_experts = self.filter_know_experts(model, selected_experts)
                if new_experts:
                    self.store_contact_avis_enquete(model, new_experts)
                    self.envoyer_avis_enquete(model, new_experts)
                    self.send_avis_enquete_mails(model, new_experts)
                flash(
                    "Votre avis d'enquête a été envoyé aux contacts sélectionnés",
                    "success",
                )
                response = Response("")
                response.headers["HX-Redirect"] = url_for("AvisEnqueteWipView:index")
                return response
            case "update":
                form.update_experts()
                form.save_state()
            case "add":
                form.add_experts()
                form.save_state()
            case "":
                pass
            case _:
                msg = f"Invalid action: {action}"
                raise ValueError(msg)

        experts = form.get_selectable_experts()
        selected_experts = form.get_selected_experts()

        ctx = {
            "form": form,
            "experts": experts,
            "selected_experts": selected_experts,
            "title": title,
            "model": model,
        }

        html = render_template("wip/avis_enquete/ciblage.j2", **ctx)
        html = extract_fragment(html, "main")
        return html

    def filter_know_experts(
        self, model: AvisEnquete, selected_experts: list[User]
    ) -> list[User]:
        repo = container.get(ContactAvisEnqueteRepository)
        contacts = repo.list(avis_enquete_id=model.id)
        known_expert_ids = {contact.expert_id for contact in contacts}
        return [e for e in selected_experts if e.id not in known_expert_ids]

    def store_contact_avis_enquete(
        self, model: AvisEnquete, selected_experts: list[User]
    ) -> None:
        repo = container.get(ContactAvisEnqueteRepository)

        contacts = [
            ContactAvisEnquete(
                avis_enquete=model,
                journaliste=model.owner,
                expert=expert,
            )
            for expert in selected_experts
        ]
        repo.add_many(contacts)

    def envoyer_avis_enquete(
        self, model: AvisEnquete, selected_experts: list[User]
    ) -> None:
        notification_service = container.get(NotificationService)

        for expert_user in selected_experts:
            message = f"Un nouvel avis d'enquête est disponible: {model.title}"
            url = "#TODO"
            notification_service.post(expert_user, message, url)

        db_session = container.get(scoped_session)
        db_session.commit()

    def send_avis_enquete_mails(
        self, model: AvisEnquete, selected_experts: list[User]
    ) -> None:
        actual_sender = cast("User", current_user)
        sender_name = actual_sender.email
        organisation = actual_sender.organisation
        # user sending Avis d Enquete shall have and organisation
        org_name = organisation.name if organisation else "inconnue"
        abstract = model.title

        for expert_user in selected_experts:
            recipient = expert_user.email
            notification_mail = AvisEnqueteNotificationMail(
                sender="contact@aipress24.com",
                recipient=recipient,
                sender_name=sender_name,
                bw_name=org_name,
                abstract=abstract,
            )
            notification_mail.send()

    @route("/<id>/reponses", methods=["GET"])
    def reponses(self, id):
        model = self._get_model(id)
        title = f"Gestion des réponses - {model.title}"
        self.update_breadcrumbs(label=title)

        # Fetch responses from ContactAvisEnquete
        db_session = container.get(scoped_session)
        responses = (
            db_session.query(ContactAvisEnquete)
            .filter(ContactAvisEnquete.avis_enquete_id == model.id)
            .all()
        )

        ctx = {
            "title": title,
            "model": model,
            "responses": responses,
        }

        html = render_template("wip/avis_enquete/reponses.j2", **ctx)
        return html

    @route("/<id>/rdv", methods=["GET"])
    def rdv(self, id):
        model = self._get_model(id)
        title = f"Gestion des rendez-vous - {model.title}"
        self.update_breadcrumbs(label=title)

        ctx = {
            "title": title,
            "model": model,
        }

        html = render_template("wip/avis_enquete/rdv.j2", **ctx)
        return html

    @route("/<id>/rdv-propose/<contact_id>", methods=["GET", "POST"])
    def rdv_propose(self, id, contact_id):
        model = self._get_model(id)
        db_session = container.get(scoped_session)

        # Fetch the contact response
        contact = db_session.query(ContactAvisEnquete).get(contact_id)
        if not contact or contact.avis_enquete_id != model.id:
            flash("Contact introuvable", "error")
            return Response(
                "",
                headers={"HX-Redirect": url_for("AvisEnqueteWipView:reponses", id=id)},
            )

        if request.method == "POST":
            # Handle form submission
            from datetime import datetime

            from app.modules.wip.models.newsroom.avis_enquete import RDVType

            rdv_type = RDVType[request.form.get("rdv_type")]
            rdv_phone = request.form.get("rdv_phone", "")
            rdv_video_link = request.form.get("rdv_video_link", "")
            rdv_address = request.form.get("rdv_address", "")
            rdv_notes = request.form.get("rdv_notes", "")

            # Collect proposed slots and convert to datetime objects
            proposed_slots = []
            for i in range(1, 6):  # Support up to 5 slots
                slot_date = request.form.get(f"slot_date_{i}")
                slot_time = request.form.get(f"slot_time_{i}")
                if slot_date and slot_time:
                    try:
                        # Parse string to datetime object
                        slot_str = f"{slot_date}T{slot_time}"
                        slot_dt = datetime.fromisoformat(slot_str)
                        proposed_slots.append(slot_dt)
                    except ValueError:
                        flash(
                            f"Format de date/heure invalide pour le créneau {i}",
                            "error",
                        )
                        return Response(
                            "",
                            headers={
                                "HX-Redirect": url_for(
                                    "AvisEnqueteWipView:rdv_propose",
                                    id=id,
                                    contact_id=contact_id,
                                )
                            },
                        )

            # Use business method to propose RDV (includes validation)
            try:
                contact.propose_rdv(
                    rdv_type=rdv_type,
                    proposed_slots=proposed_slots,
                    rdv_phone=rdv_phone,
                    rdv_video_link=rdv_video_link,
                    rdv_address=rdv_address,
                    rdv_notes=rdv_notes,
                )
                db_session.commit()
            except ValueError as e:
                flash(str(e), "error")
                return Response(
                    "",
                    headers={
                        "HX-Redirect": url_for(
                            "AvisEnqueteWipView:rdv_propose",
                            id=id,
                            contact_id=contact_id,
                        )
                    },
                )

            # Send notification to expert
            notification_service = container.get(NotificationService)
            message = (
                f"Proposition de rendez-vous pour l'avis d'enquête : {model.title}"
            )
            notification_url = url_for(
                "AvisEnqueteWipView:rdv_accept", id=model.id, contact_id=contact.id
            )
            notification_service.post(contact.expert, message, notification_url)
            db_session.commit()

            flash("Votre proposition de rendez-vous a été envoyée", "success")
            return Response(
                "",
                headers={"HX-Redirect": url_for("AvisEnqueteWipView:reponses", id=id)},
            )

        title = f"Proposer un RDV - {contact.expert.full_name}"
        self.update_breadcrumbs(label=title)

        ctx = {
            "title": title,
            "model": model,
            "contact": contact,
        }

        html = render_template("wip/avis_enquete/rdv_propose.j2", **ctx)
        return html

    @route("/<id>/rdv-accept/<contact_id>", methods=["GET", "POST"])
    def rdv_accept(self, id, contact_id):
        """Expert view to accept a proposed RDV slot"""
        model = self._get_model(id)
        db_session = container.get(scoped_session)

        # Fetch the contact response
        contact = db_session.query(ContactAvisEnquete).get(contact_id)
        if not contact or contact.avis_enquete_id != model.id:
            flash("Contact introuvable", "error")
            return Response("", headers={"HX-Redirect": url_for("home")})

        # Verify that the current user is the expert
        session_service = container.get(SessionService)
        current_user = session_service.user
        if current_user.id != contact.expert_id:
            flash("Vous n'êtes pas autorisé à accéder à cette page", "error")
            return Response("", headers={"HX-Redirect": url_for("home")})

        if request.method == "POST":
            # Handle slot acceptance
            from datetime import datetime

            selected_slot_str = request.form.get("selected_slot")
            expert_notes = request.form.get("expert_notes", "")

            if not selected_slot_str:
                flash("Aucun créneau sélectionné", "error")
                return Response(
                    "",
                    headers={
                        "HX-Redirect": url_for(
                            "AvisEnqueteWipView:rdv_accept",
                            id=id,
                            contact_id=contact_id,
                        )
                    },
                )

            # Convert selected slot string to datetime object
            try:
                selected_slot = datetime.fromisoformat(selected_slot_str)
            except ValueError:
                flash("Format de créneau invalide", "error")
                return Response(
                    "",
                    headers={
                        "HX-Redirect": url_for(
                            "AvisEnqueteWipView:rdv_accept",
                            id=id,
                            contact_id=contact_id,
                        )
                    },
                )

            # Use business method to accept RDV (includes validation)
            try:
                contact.accept_rdv(selected_slot, expert_notes=expert_notes)
                db_session.commit()
            except ValueError as e:
                flash(str(e), "error")
                return Response(
                    "",
                    headers={
                        "HX-Redirect": url_for(
                            "AvisEnqueteWipView:rdv_accept",
                            id=id,
                            contact_id=contact_id,
                        )
                    },
                )

            # Send notification to journalist
            notification_service = container.get(NotificationService)
            journalist = contact.journaliste
            message = f"{contact.expert.full_name} a accepté un créneau pour le RDV"
            notification_url = url_for("AvisEnqueteWipView:reponses", id=model.id)
            notification_service.post(journalist, message, notification_url)
            db_session.commit()

            flash(
                "Vous avez accepté le rendez-vous. Le journaliste sera notifié.",
                "success",
            )
            return Response("", headers={"HX-Redirect": url_for("home")})

        title = f"Accepter un rendez-vous - {model.title}"
        self.update_breadcrumbs(label=title)

        ctx = {
            "title": title,
            "model": model,
            "contact": contact,
        }

        html = render_template("wip/avis_enquete/rdv_accept.j2", **ctx)
        return html


class SearchForm:
    state: dict[str, str | list[str]]
    selectors: list[Selector]
    all_experts: list[User]

    def __init__(self) -> None:
        self.selector_keys: list[str] = [s.id for s in self._selector_classes]
        self._restore_state()
        self._update_state()
        self.selectors = self._get_selectors()
        self.all_experts = self._get_all_users()
        # self.tailles_orga = get_full_taxonomy("taille_organisation")

    def _restore_state(self) -> None:
        session = container.get(SessionService)
        self.state = session.get("newsroom:ciblage", {})

    def _update_state(self) -> None:
        if not request.headers.get("HX-Request"):
            # initialization
            return

        data_source = request.args if request.method == "GET" else request.form
        seen_selectors: set[str] = set()

        for k, values in data_source.lists():
            if k.startswith(("action:", "expert:")):
                continue
            clean_values = [v for v in values if v]
            if clean_values:
                self.state[k] = clean_values
                seen_selectors.add(k)

        for key in self.selector_keys:
            if key not in seen_selectors:
                self.state.pop(key, None)

    def save_state(self) -> None:
        session = container.get(SessionService)
        session["newsroom:ciblage"] = self.state
        warn("self.state saved", self.state)

    def get_action(self) -> str:
        for name in request.form.to_dict():
            if name.startswith("action:"):
                return name.split(":")[1]
        return ""

    def add_experts(self) -> None:
        expert_ids = list(self.get_expert_ids())
        expert_ids.extend(self.state.get("selected_experts", []))
        self.state["selected_experts"] = list(set(expert_ids))

    def update_experts(self) -> None:
        expert_ids = list(self.get_expert_ids())
        self.state["selected_experts"] = expert_ids

    def get_expert_ids(self) -> Generator[int]:
        form_data = request.form.to_dict()
        for k in form_data:
            if k.startswith("expert:"):
                yield int(k.split(":")[1])

    def get_selectable_experts(self) -> list[User]:
        # return all expert if no selection filter
        if all(not self.state.get(selector.id) for selector in self.selectors):
            return self.all_experts[:MAX_SELECTABLE_EXPERTS]

        experts = self.all_experts
        for selector in self.selectors:
            warn(selector.id)
            selected_values = self.state.get(selector.id)
            if not selected_values:
                continue
            criteria = (
                set(selected_values)
                if isinstance(selected_values, list)
                else {selected_values}
            )
            experts = selector.filter_experts(criteria, experts)

        selected_ids = set(self.state.get("selected_experts", []))
        new_experts = [e for e in experts if e.id not in selected_ids]

        new_experts.sort(key=lambda e: (e.last_name, e.first_name))
        return new_experts[:MAX_SELECTABLE_EXPERTS]

    def get_selected_experts(self) -> list[User]:
        selected_expert_ids = set(self.state.get("selected_experts", []))
        user_repo = container.get(UserRepository)
        experts = user_repo.list()
        experts = [e for e in experts if e.id in selected_expert_ids]
        return experts

    @property
    def _selector_classes(self) -> list[type]:
        return [
            SecteurSelector,
            MetierSelector,
            FonctionSelector,
            TypeOrganisationSelector,
            TailleOrganisationSelector,
            PaysSelector,
            DepartementSelector,
            VilleSelector,
        ]

    def _get_selectors(self) -> list[Selector]:
        return [klass(self) for klass in self._selector_classes]

    def _get_all_users(self) -> list[User]:
        user_repo = container.get(UserRepository)
        users = user_repo.list()
        return users


class Selector(abc.ABC):
    form: SearchForm
    id: str
    label: str
    values: set[str]  # selected items

    def __init__(self, form: SearchForm) -> None:
        self.form = form
        raw_values = form.state.get(self.id, [])
        if isinstance(raw_values, list):
            self.values = set(raw_values)
        elif raw_values:
            self.values = {raw_values}
        else:
            self.values = set()

    @property
    def options(self) -> list[Option]:
        choice_values = self.get_values()
        return self._make_options(choice_values)[:MAX_OPTIONS]

    @abstractmethod
    def get_values(self) -> set[str]:
        pass

    @abstractmethod
    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        pass

    def _make_options(self, values: list[str] | set[str]) -> list[Option]:
        options: set[Option] = set()
        for value in values:
            selected = "selected" if value in self.values else ""
            option = Option(value, value, selected)
            options.add(option)
        return sorted(options, key=self.sorter)

    def sorter(self, option: Option) -> str:
        def remove_diacritics(input_str: str):
            # Normalize the string to decompose characters with diacritics
            normalized_str = unicodedata.normalize("NFKD", input_str)
            # Filter out non-ASCII characters
            ascii_str = "".join(
                c for c in normalized_str if unicodedata.category(c) != "Mn"
            )
            return ascii_str

        return remove_diacritics(option.label)


class SecteurSelector(Selector):
    id = "secteur"
    label = "Secteur d'activité"

    def get_values(self) -> set[str]:
        merged_values: set[str] = set()
        for expert in self.form.all_experts:
            merged_values.update(expert.profile.secteurs_activite)
        return merged_values

    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        if not criteria:
            return experts
        return [
            e
            for e in experts
            if not e.profile.secteurs_activite
            or any(x in criteria for x in e.profile.secteurs_activite)
        ]


class MetierSelector(Selector):
    id = "metier"
    label = "Métier"

    def get_values(self) -> set[str]:
        merged_values: set[str] = set()
        for expert in self.form.all_experts:
            merged_values.update(expert.tous_metiers)
        return merged_values

    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        if not criteria:
            return experts
        return [
            e
            for e in experts
            if not e.tous_metiers or any(x in criteria for x in e.tous_metiers)
        ]


class FonctionSelector(Selector):
    id = "fonction"
    label = "Fonction"

    def get_values(self) -> set[str]:
        merged_values: set[str] = set()
        for expert in self.form.all_experts:
            merged_values.update(expert.profile.toutes_fonctions)
        return merged_values

    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        if not criteria:
            return experts
        return [
            e
            for e in experts
            if not e.profile.toutes_fonctions
            or any(x in criteria for x in e.profile.toutes_fonctions)
        ]


class TypeOrganisationSelector(Selector):
    id = "type_organisation"
    label = "Type d'organisation"

    def get_values(self) -> set[str]:
        merged_values: set[str] = set()
        for expert in self.form.all_experts:
            merged_values.update(expert.profile.type_organisation)
        return merged_values

    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        if not criteria:
            return experts
        return [
            e
            for e in experts
            if not e.profile.type_organisation
            or any(x in criteria for x in e.profile.type_organisation)
        ]


class TailleOrganisationSelector(Selector):
    id = "taille_organisation"
    label = "Taille de l'organisation"

    def get_values(self) -> set[str]:
        merged_values: set[str] = set()
        for expert in self.form.all_experts:
            merged_values.update(expert.profile.taille_organisation)
        return merged_values

    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        if not criteria:
            return experts
        return [
            e
            for e in experts
            if any(x in criteria for x in e.profile.taille_organisation)
        ]


class PaysSelector(Selector):
    id = "pays"
    label = "Pays"

    def get_values(self) -> set[str]:
        return {e.profile.country for e in self.form.all_experts}

    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if e.profile.country in criteria]


class DepartementSelector(Selector):
    id = "departement"
    label = "Département"

    def get_values(self) -> set[str]:
        selected_countries = self.form.state.get("pays")
        if not selected_countries:
            return []
        if isinstance(selected_countries, str):
            country_criteria = {selected_countries}
        else:
            country_criteria = set(selected_countries)
        return {
            u.profile.departement
            for u in self.form.all_experts
            if u.profile.country in country_criteria
        }

    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if e.profile.departement in criteria]


class VilleSelector(Selector):
    id = "ville"
    label = "Ville"

    def get_values(self) -> set[str]:
        selected_departements = self.form.state.get("departement")
        if not selected_departements:
            return []
        if isinstance(selected_departements, str):
            departement_criteria = {selected_departements}
        else:
            departement_criteria = set(selected_departements)
        return {
            u.profile.ville
            for u in self.form.all_experts
            if u.profile.departement in departement_criteria
        }

    def filter_experts(self, criteria: set[str], experts: list[User]) -> list[User]:
        if not criteria:
            return experts
        return [e for e in experts if e.profile.ville in criteria]


@frozen(order=True)
class Option:
    id: str
    label: str
    selected: str = ""


@register
def register_on_app(app: Flask) -> None:
    AvisEnqueteWipView.register(app)
