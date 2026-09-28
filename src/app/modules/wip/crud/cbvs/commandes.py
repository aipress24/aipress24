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
from typing import cast

from flask import Flask, flash, g, redirect
from flask_classful import route
from flask_super.registry import register
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from werkzeug import Response
from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.flask.extensions import db
from app.models.auth import Role, User
from app.models.errors import BusinessRuleError
from app.models.repositories import UserRepository
from app.modules.wip.models import Commande, CommandeRepository
from app.modules.wip.pr_access import user_can_access_newsroom
from app.modules.wip.redac_chef import redac_chef_media_id
from app.modules.wip.services.newsroom.commande_notifications import (
    notify_destinataire,
)
from app.modules.wip.services.pr_notifications import absolute_url_for

from ._base import BaseWipView, assign_publisher
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
        actions.append({"label": "Supprimer", "url": self.url_for(item, "delete")})
        return actions


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
