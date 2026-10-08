# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WORK/NEWSROOM/Commandes.

A commande belongs to whoever places it (`owner_id`): a rédac chef or
equivalent within a media. That person edits, validates, cancels and
deletes it. Its destinataire, the journalist who will write it, and the
other rédac chefs of the media it is placed for only read it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from app.modules.kyc.lib.country_select import CountrySelectField

from flask import Flask, flash, g, redirect, request, url_for
from flask_classful import route
from flask_super.registry import register
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from werkzeug import Response
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.templates import templated
from app.logging import report_failure
from app.models.auth import Role, User
from app.models.errors import BusinessRuleError
from app.models.lifecycle import PublicationStatus
from app.models.repositories import UserRepository
from app.modules.wip.models import Commande, CommandeRepository
from app.modules.wip.models.newsroom.sujet import Sujet
from app.modules.wip.pr_access import user_can_access_newsroom
from app.modules.wip.redac_chef import is_redac_chef_of_org, redac_chef_media_id
from app.modules.wip.services.newsroom.commande_notifications import (
    notify_destinataire,
)
from app.modules.wip.services.newsroom.sujet_accept import (
    notify_author_of_sujet_acceptance,
)
from app.modules.wip.services.pr_notifications import absolute_url_for

from ._base import UPDATE_TEMPLATE, BaseWipView, assign_publisher
from ._forms import CommandeForm
from ._table import BaseDataSource, BaseTable


class CommandeDataSource(BaseDataSource):
    """Lists the commandes the user may read (`Commande.is_visible_to`)."""

    def _base_query(self):
        stmt = (
            select(Commande)
            .where(Commande.is_visible_to(g.user.id, redac_chef_media_id(g.user)))
            .where(Commande.deleted_at.is_(None))
        )
        if self.q:
            stmt = stmt.where(Commande.titre.ilike(f"%{self.q}%"))
        return stmt

    def get_count(self) -> int:
        stmt = select(func.count()).select_from(self._base_query().subquery())
        return db.session.scalar(stmt) or 0


class CommandesTable(BaseTable):
    view_class = "CommandesWipView"
    id = "commandes-table"

    def __init__(self, q="") -> None:
        super().__init__(Commande, q)

    def _make_datasource(self, model_class: type, q: str) -> BaseDataSource:
        return CommandeDataSource(model_class=model_class, q=q)

    def get_status_label(self, obj: Commande) -> str:
        return obj.status_label

    def get_actions(self, item: Commande) -> list[dict]:
        """Whoever placed the commande runs it; everyone else only reads it."""
        actions = [{"label": "Voir", "url": self.url_for(item)}]
        if item.owner_id != g.user.id:
            return actions
        actions.append({"label": "Modifier", "url": self.url_for(item, "edit")})
        if item.can_validate():
            actions.append(
                {
                    "label": "Valider",
                    "url": self.url_for(item, "validate"),
                    "method": "post",
                }
            )
        if item.can_cancel():
            actions.append(
                {
                    "label": "Annuler",
                    "url": self.url_for(item, "cancel"),
                    "method": "post",
                }
            )
        actions.append(
            {
                "label": "Supprimer",
                "url": self.url_for(item, "delete"),
                "method": "post",
            }
        )
        return actions


# Surface the step-nav bar on the Voir / Modifier pages.
# language=jinja2
_COMMANDE_VOIR_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% from "wip/_step_nav_simple.j2" import step_nav_simple %}
{% block body_content %}
  {{ step_nav_simple(commande, "CommandesWipView", "voir", "commandes", can_edit) }}
  {{ form_rendered|safe }}
  {{ extra_view_html|safe }}
  {{ step_nav_simple(commande, "CommandesWipView", "voir", "commandes", can_edit) }}
{% endblock %}
"""

# language=jinja2
_COMMANDE_MODIFIER_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% from "wip/_step_nav_simple.j2" import step_nav_simple %}
{% block body_content %}
  {{ step_nav_simple(commande, "CommandesWipView", "modifier", "commandes") }}
  {{ form_rendered|safe }}
  {{ step_nav_simple(commande, "CommandesWipView", "modifier", "commandes") }}
{% endblock %}
"""


class CommandesWipView(BaseWipView):
    name = "commandes"

    model_class = Commande
    repo_class = CommandeRepository
    table_class = CommandesTable
    form_class = CommandeForm
    doc_type = "commande"

    route_base = "commandes"
    path = "/wip/commandes/"

    # UI
    label_main = "Newsroom: commandes"
    label_list = "Liste des commandes"
    label_new = "Créer une commande"
    label_view = "Voir la commande"
    label_edit = "Modifier la commande"
    table_id = "commande-table-body"

    msg_delete_ok = "La commande a été supprimée"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer cette commande"
    msg_cannot_edit = "Seul le commanditaire peut modifier cette commande"

    icon = "newspaper"

    def before_request(self, *_args, **_kwargs) -> Response | None:
        if resp := super().before_request(*_args, **_kwargs):
            return resp

        if not user_can_access_newsroom(g.user):
            raise Forbidden
        return None

    @templated(_COMMANDE_VOIR_TEMPLATE)
    def get(self, id):
        """Step « Voir » — wrapped with the step-nav bar."""
        model = self._get_model(id)
        title = f"{self.label_view} '{model.title}'"
        ctx = self._view_ctx(model, title=title, mode="view")
        ctx["commande"] = model
        ctx["can_edit"] = self._can_edit(model)
        return ctx

    @templated(_COMMANDE_MODIFIER_TEMPLATE)
    def edit(self, id):
        """Step « Modifier » — wrapped with the step-nav bar."""
        model = self._get_model(id)
        if not self._can_edit(model):
            flash(self.msg_cannot_edit, "error")
            return redirect(self._url_for("get", id=id))
        title = f"{self.label_edit} '{model.title}'"
        ctx = self._view_ctx(model, title=title)
        ctx["commande"] = model
        return ctx

    @templated(UPDATE_TEMPLATE)
    def new(self) -> dict | Response:
        from_sujet_id = request.args.get("from_sujet")
        if from_sujet_id:
            try:
                sujet_id = int(from_sujet_id)
            except (ValueError, TypeError):
                flash("Identifiant de sujet invalide", "error")
                return redirect(self._url_for("index"))

            sujet = db.session.get(Sujet, sujet_id)
            if not sujet:
                flash("Sujet introuvable", "error")
                return redirect(self._url_for("index"))
            if not is_redac_chef_of_org(g.user, sujet.media_id):
                flash("Vous n'êtes pas autorisé à accepter ce sujet", "error")
                return redirect(self._url_for("index"))
            if sujet.status != PublicationStatus.PUBLIC:
                flash("Ce sujet n'est pas disponible pour acceptation", "error")
                return redirect(self._url_for("index"))

            commande = Commande(
                owner_id=g.user.id,
                commanditaire_id=g.user.id,
                destinataire_id=sujet.owner_id,
                media_id=sujet.media_id,
                publisher_id=sujet.media_id,
                titre=sujet.titre,
                contenu=sujet.contenu,
                brief=sujet.brief or "",
                status=PublicationStatus.DRAFT,
                date_limite_validite=sujet.date_limite_validite,
                date_bouclage=sujet.date_parution_prevue,
                # date_parution_prevue left empty: rédac chef to enter it
                genre=sujet.genre or "",
                section=sujet.section or "",
                topic=sujet.topic or "",
                sector=sujet.sector or "",
                pays_zip_ville=sujet.pays_zip_ville or "",
                pays_zip_ville_detail=sujet.pays_zip_ville_detail or "",
            )
            form = self.form_class(obj=commande)
            self._make_media_choices(form)
            self._make_extra_choices(form)
            self._make_country_choices(form)
            if sujet.media_id and not any(
                str(c[0]) == str(sujet.media_id) for c in form.media_id.choices
            ):
                if getattr(sujet, "media", None):
                    media_name = sujet.media.name
                else:
                    media_name = f"Organisation {sujet.media_id}"
                form.media_id.choices.append((str(sujet.media_id), media_name))
            if sujet.owner_id and not any(
                str(c[0]) == str(sujet.owner_id) for c in form.destinataire_id.choices
            ):
                if getattr(sujet, "owner", None):
                    owner_name = sujet.owner.full_name
                else:
                    owner_name = f"Utilisateur {sujet.owner_id}"
                form.destinataire_id.choices.append((sujet.owner_id, owner_name))
            for field_name in ("genre", "section", "topic", "sector"):
                field = getattr(form, field_name, None)
                if field is not None:
                    val = getattr(sujet, field_name, None)
                    if val and not any(str(c[0]) == str(val) for c in field.choices):
                        field.choices.append((val, val))
            form.destinataire_id.data = sujet.owner_id
            form.media_id.data = str(sujet.media_id)
            if hasattr(form, "pays_zip_ville"):
                pzv = cast("CountrySelectField", form.pays_zip_ville)
                pzv.data2 = sujet.pays_zip_ville_detail

            action_url = url_for("CommandesWipView:post", from_sujet=sujet_id)
            return self._view_ctx(
                model=commande,
                form=form,
                title="Accepter le sujet et créer la commande",
                action_url=action_url,
            )

        return super().new()

    @templated(UPDATE_TEMPLATE)
    def post(self) -> Response | dict:
        from_sujet_id = request.args.get("from_sujet")
        if not from_sujet_id:
            return super().post()

        form_data = request.form
        if form_data.get("_action") == "cancel":
            return redirect(url_for("SujetsWipView:index"))

        try:
            sujet_id = int(from_sujet_id)
        except (ValueError, TypeError):
            flash("Identifiant de sujet invalide", "error")
            return redirect(self._url_for("index"))

        sujet = db.session.get(Sujet, sujet_id)
        if not sujet or sujet.status != PublicationStatus.PUBLIC:
            flash("Ce sujet n'est plus disponible pour acceptation", "error")
            return redirect(url_for("SujetsWipView:index"))

        if not is_redac_chef_of_org(g.user, sujet.media_id):
            flash("Vous n'êtes pas autorisé à accepter ce sujet", "error")
            return redirect(url_for("SujetsWipView:index"))

        model = self.model_class()
        model.owner = g.user
        model.commanditaire_id = g.user.id
        model.destinataire_id = sujet.owner_id
        model.publisher_id = sujet.media_id
        model.brief = sujet.brief or ""
        if media_id_str := request.form.get("media_id"):
            model.media_id = int(media_id_str)

        form = self.form_class(form_data)
        self._make_media_choices(form)
        self._make_extra_choices(form)
        self._make_country_choices(form)
        if sujet.media_id and not any(
            str(c[0]) == str(sujet.media_id) for c in form.media_id.choices
        ):
            if getattr(sujet, "media", None):
                media_name = sujet.media.name
            else:
                media_name = f"Organisation {sujet.media_id}"
            form.media_id.choices.append((str(sujet.media_id), media_name))
        if sujet.owner_id and not any(
            str(c[0]) == str(sujet.owner_id) for c in form.destinataire_id.choices
        ):
            if getattr(sujet, "owner", None):
                owner_name = sujet.owner.full_name
            else:
                owner_name = f"Utilisateur {sujet.owner_id}"
            form.destinataire_id.choices.append((sujet.owner_id, owner_name))
        for field_name in ("genre", "section", "topic", "sector"):
            field = getattr(form, field_name, None)
            if field is not None:
                val = request.form.get(field_name) or getattr(sujet, field_name, None)
                if val and not any(str(c[0]) == str(val) for c in field.choices):
                    field.choices.append((val, val))

        action_url = url_for("CommandesWipView:post", from_sujet=from_sujet_id)
        if not form.validate():
            return self._view_ctx(
                model=model,
                form=form,
                action_url=action_url,
                title="Accepter le sujet et créer la commande",
            )

        form.populate_obj(model)
        if hasattr(model, "pays_zip_ville"):
            model.pays_zip_ville_detail = request.form.get("pays_zip_ville_detail", "")
        if hasattr(model, "media_id"):
            model.media_id = int(model.media_id)

        self._normalize_model_datetimes(model)
        try:
            self._post_update_model(model)
        except BusinessRuleError as exc:
            flash(str(exc), "error")
            return self._view_ctx(
                model=model,
                form=form,
                action_url=action_url,
                title="Accepter le sujet et créer la commande",
            )

        repo = self._get_repo()
        repo.add(model, auto_commit=True)

        sujet.status = PublicationStatus.ACCEPTED
        db.session.commit()

        author = getattr(sujet, "owner", None)
        if author is not None:
            commande_url = absolute_url_for("CommandesWipView:get", id=model.id)
            notify_author_of_sujet_acceptance(
                author=author,
                accepter=g.user,
                sujet_title=sujet.titre,
                commande_url=commande_url,
            )
            db.session.commit()
            if author.email:
                try:
                    accepter_org = getattr(g.user, "organisation", None)
                    accepter_org_name = (
                        getattr(accepter_org, "bw_name", None)
                        or getattr(accepter_org, "name", None)
                        or ""
                    )
                    from app.services.emails import SujetAcceptanceNotificationMail

                    mail = SujetAcceptanceNotificationMail(
                        sender="contact@aipress24.com",
                        recipient=author.email,
                        sender_mail=g.user.email,
                        accepter_full_name=g.user.full_name,
                        accepter_organisation=accepter_org_name,
                        sujet_title=sujet.titre,
                        commande_url=commande_url,
                    )
                    mail.send()
                except Exception as exc:
                    report_failure(
                        f"sujet acceptance mail failed (sujet {sujet.id})", exc
                    )

        flash("Sujet accepté : la commande a été créée et l'auteur notifié.")
        return redirect(self._url_for("index"))

    @route("/<id>/validate/", methods=["POST"])
    def validate(self, id):
        """The commanditaire validates the commande."""
        return self._change_status(id, Commande.validate, "Commande validée.")

    @route("/<id>/cancel/", methods=["POST"])
    def cancel(self, id):
        """The commanditaire cancels the commande."""
        return self._change_status(id, Commande.cancel, "Commande annulée.")

    def _change_status(
        self, id, transition: Callable[[Commande], None], done: str
    ) -> Response:
        """Run `transition`, then tell the destinataire by bell and by mail."""
        commande = self._get_placed_commande(id)
        try:
            transition(commande)
        except BusinessRuleError as exc:
            flash(str(exc), "error")
            return redirect(self._url_for("get", id=id))
        db.session.commit()

        commande_url = absolute_url_for("CommandesWipView:get", id=commande.id)
        notify_destinataire(commande, g.user, commande_url)
        db.session.commit()
        flash(done)
        return redirect(self._url_for("index"))

    def _get_placed_commande(self, id) -> Commande:
        """The commande `id`, which only the one who placed it may run."""
        commande = cast("Commande", self._get_model(id))
        if not self._can_edit(commande):
            raise Forbidden
        return commande

    def _can_access(self, model: Commande) -> bool:
        return model.is_visible_to(g.user.id, redac_chef_media_id(g.user))

    def _can_edit(self, model: Commande) -> bool:
        return model.owner_id == g.user.id

    def _make_extra_choices(self, form) -> None:
        form.destinataire_id.choices = _destinataire_choices()

    def _post_update_model(self, model: Commande) -> None:
        assign_publisher(model)


def _destinataire_choices() -> list[tuple[int | str, str]]:
    """Every listable journalist, by name, after an empty prompt."""
    stmt = (
        select(User)
        .options(selectinload(User.organisation))
        .where(*UserRepository.public_member_filters())
        .where(User.roles.any(Role.name == RoleEnum.PRESS_MEDIA.name))
        .order_by(User.last_name, User.first_name)
    )
    choices: list[tuple[int | str, str]] = [("", "Choisir un journaliste")]
    for user in db.session.scalars(stmt):
        org = user.organisation
        org_name = (org.bw_name or org.name) if org else ""
        label = f"{user.full_name} — {org_name}" if org_name else user.full_name
        choices.append((user.id, label))
    return choices


@register
def register_on_app(app: Flask) -> None:
    CommandesWipView.register(app)
