# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from abc import abstractmethod
from collections.abc import Generator

from attr import frozen
from flask import Flask, Response, flash, render_template, request
from flask_classful import route
from flask_super.registry import register
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.enums import RoleEnum
from app.flask.lib.htmx import extract_fragment
from app.flask.routing import url_for
from app.models.auth import User
from app.models.repositories import AvisEnqueteRepository, UserRepository
from app.modules.wip.models.newsroom import AvisEnquete
from app.services.geonames import get_dept_name, is_dept_in_region
from app.services.notifications import NotificationService
from app.services.sessions import SessionService
from app.services.taxonomies import get_taxonomy

from ._base import BaseWipView
from ._forms import AvisEnqueteForm
from ._table import BaseTable


class AvisEnqueteTable(BaseTable):
    id = "avis-enquete-table"

    def __init__(self, q=""):
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
        model = self._get_model(id)
        title = f"Ciblage des contacts - {model.title}"
        self.update_breadcrumbs(label=model.title)

        form = SearchForm()
        action = form.get_action()

        match action:
            case "confirm":
                self.envoyer_avis_enquete(model, form.get_selected_experts())
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
                raise ValueError(f"Invalid action: {action}")

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

    def envoyer_avis_enquete(self, model, selected_experts):
        notification_service = container.get(NotificationService)

        for _expert in selected_experts:
            message = f"Un nouvel avis d'enquête est disponible: {model.title}"
            url = "#TODO"
            notification_service.post(_expert, message, url)

        db_session = container.get(scoped_session)
        db_session.commit()

    @route("/<id>/reponses", methods=["GET"])
    def reponses(self, id):
        model = self._get_model(id)
        title = f"Gestion des réponses - {model.title}"
        self.update_breadcrumbs(label=title)

        ctx = {
            "title": title,
            "model": model,
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


class SearchForm:
    state: dict[str, str | list[str]]
    selectors: list[Selector]
    all_experts: list[User]

    def __init__(self):
        self._restore_state()
        self._update_state()
        self.selectors = self._get_selectors()
        self.all_experts = self._get_all_experts()

    def _restore_state(self):
        session = container.get(SessionService)
        self.state = session.get("newsroom:ciblage", {})

    def _update_state(self):
        for k, v in request.form.to_dict().items():
            if k.startswith("action:"):
                continue
            if k.startswith("expert:"):
                continue
            self.state[k] = v

    def save_state(self):
        session = container.get(SessionService)
        session["newsroom:ciblage"] = self.state

    def get_action(self) -> str:
        for name in request.form.to_dict():
            if name.startswith("action:"):
                return name.split(":")[1]
        return ""

    def add_experts(self):
        expert_ids = list(self.get_expert_ids())
        expert_ids.extend(self.state.get("selected_experts", []))
        self.state["selected_experts"] = list(set(expert_ids))

    def update_experts(self):
        expert_ids = list(self.get_expert_ids())
        self.state["selected_experts"] = expert_ids

    def get_expert_ids(self) -> Generator[int]:
        form_data = request.form.to_dict()
        for k in form_data:
            if k.startswith("expert:"):
                yield int(k.split(":")[1])

    def get_selectable_experts(self):
        experts = self.all_experts

        if all(not self.state.get(selector.id) for selector in self.selectors):
            return []

        for selector in self.selectors:
            value = self.state.get(selector.id)
            if not value:
                continue
            if selector.id == "metier":
                experts = [e for e in experts if e.job_title == value]
            if selector.id == "region":
                experts = [e for e in experts if e.region == value]
            if selector.id == "departement":
                experts = [e for e in experts if e.departement == value]

        experts = [
            e for e in experts if e.id not in self.state.get("selected_experts", [])
        ]

        experts.sort(key=lambda e: (e.last_name, e.first_name))
        if len(experts) > 50:
            experts = experts[:50]

        return experts

    def get_selected_experts(self):
        selected_expert_ids = self.state.get("selected_experts", [])
        user_repo = container.get(UserRepository)
        experts = user_repo.list()
        experts = [e for e in experts if e.id in selected_expert_ids]
        return experts

    def _get_selectors(self):
        return [
            SecteurSelector(self),
            MetierSelector(self),
            FonctionSelector(self),
            TypeOrganisationSelector(self),
            TailleOrganisationSelector(self),
            RegionSelector(self),
            DepartementSelector(self),
            VilleSelector(self),
        ]

    def _get_all_experts(self):
        user_repo = container.get(UserRepository)
        users = user_repo.list()
        experts = [u for u in users if u.has_role(RoleEnum.EXPERT)]
        return experts


class Selector(abc.ABC):
    form: SearchForm
    id: str
    label: str
    value: str

    def __init__(self, form: SearchForm):
        self.form = form
        self.value = form.state.get(self.id, "")

    @property
    def options(self):
        values = self.get_values()
        return self._make_options(values)

    @abstractmethod
    def get_values(self):
        pass

    def _make_options(self, values) -> list[Option]:
        options: set[Option] = set()
        options.add(Option("", ""))
        for value in values:
            if value == self.value:
                selected = "selected"
            else:
                selected = ""
            option = Option(value, value, selected)
            options.add(option)
        return sorted(options)

    def _get_values_from_experts(self, attr, key) -> set[str]:
        experts = self.form.all_experts
        # debug(experts[0].profile)
        values = set()
        for expert in experts:
            if attr in {"match_making", "info_professionnelle"}:
                field = getattr(expert.profile, attr)
                values |= set(field[key])
            else:
                ...  # TODO
        return values


class SecteurSelector(Selector):
    id = "secteur"
    label = "Secteur d'activité"

    def get_values(self):
        return get_taxonomy("news_sectors")


class MetierSelector(Selector):
    id = "metier"
    label = "Métier"

    def get_values(self):
        return self._get_values_from_experts("match_making", "metier")


class FonctionSelector(Selector):
    id = "fonction"
    label = "Fonction"

    def get_values(self):
        v1 = self._get_values_from_experts(
            "info_professionnelle", "fonctions_ass_syn_detail"
        )
        v2 = self._get_values_from_experts(
            "info_professionnelle", "fonctions_pol_adm_detail"
        )
        v3 = self._get_values_from_experts(
            "info_professionnelle", "fonctions_org_priv_detail"
        )
        return v1 | v2 | v3


class TailleOrganisationSelector(Selector):
    id = "taille_organisation"
    label = "Taille de l 'organisation"

    def get_values(self):
        return self._get_values_from_experts("info_professionnelle", "taille_orga")


class TypeOrganisationSelector(Selector):
    id = "type_organisation"
    label = "Type d'organisation"

    def get_values(self):
        return self._get_values_from_experts("info_professionnelle", "type_orga_detail")


class RegionSelector(Selector):
    id = "region"
    label = "Région"

    def get_values(self):
        return {e.region for e in self.form.all_experts}


class DepartementSelector(Selector):
    id = "departement"
    label = "Département"

    def get_values(self):
        values = {e.departement for e in self.form.all_experts}
        if regions := self.form.state.get("region"):
            values = {v for v in values if is_dept_in_region(v, regions)}
        return values


class VilleSelector(Selector):
    id = "ville"
    label = "Ville"

    def get_values(self):
        selected_dept = self.form.state.get("departement")
        if not selected_dept:
            return []

        selected_users = self.form.all_experts
        cities = set()
        for user in selected_users:
            dept_code = user.dept_code
            dept_name = get_dept_name(dept_code)
            if dept_name != selected_dept:
                continue

            city = user.city
            if city:
                cities.add(city)

        return cities


@frozen(order=True)
class Option:
    id: str
    label: str
    selected: str = ""


@register
def register_on_app(app: Flask):
    AvisEnqueteWipView.register(app)
