# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask, g
from flask_super.registry import register
from sqlalchemy import func, or_, select
from werkzeug import Response
from werkzeug.exceptions import Forbidden

from app.flask.extensions import db
from app.flask.routing import url_for
from app.logging import warn
from app.modules.bw.bw_activation.user_utils import (
    can_user_publish_for,
    get_selected_business_wall_for_user,
)
from app.modules.wip.models import Commande, CommandeRepository
from app.modules.wip.pr_access import user_can_access_newsroom

from ._base import BaseWipView
from ._forms import CommandeForm
from ._table import BaseDataSource, BaseTable


class CommandeDataSource(BaseDataSource):
    """Bug #0225 — a Commande must surface in BOTH newsrooms: the
    journalist who authored the originating sujet (`owner_id`) AND the
    rédac chef who accepted it (`commanditaire_id`). The generic
    `owner_id == user` clause showed it only to the journalist."""

    def _visibility_clause(self):
        M = self.model_class
        user = g.user
        return or_(M.owner_id == user.id, M.commanditaire_id == user.id)

    def _base_query(self):
        M = self.model_class
        stmt = select(M).where(self._visibility_clause()).where(M.deleted_at.is_(None))
        if self.q:
            stmt = stmt.where(M.titre.ilike(f"%{self.q}%"))
        return stmt

    def get_count(self) -> int:
        M = self.model_class
        stmt = (
            select(func.count())
            .select_from(M)
            .where(self._visibility_clause())
            .where(M.deleted_at.is_(None))
        )
        if self.q:
            stmt = stmt.where(M.titre.ilike(f"%{self.q}%"))
        return db.session.scalar(stmt) or 0


class CommandesTable(BaseTable):
    id = "commandes-table"

    def __init__(self, q="") -> None:
        super().__init__(Commande, q)

    def _make_datasource(self, model_class: type, q: str) -> BaseDataSource:
        return CommandeDataSource(model_class=model_class, q=q)

    def url_for(self, obj, _action="get", **kwargs):  # type: ignore[override]
        return url_for(f"CommandesWipView:{_action}", id=obj.id, **kwargs)


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

    icon = "newspaper"

    def before_request(self, *_args, **_kwargs) -> Response | None:
        if resp := super().before_request(*_args, **_kwargs):
            return resp

        if not user_can_access_newsroom(g.user):
            raise Forbidden
        return None

    def _post_update_model(self, model: Commande) -> None:
        if model.publisher_id and not can_user_publish_for(g.user, model.publisher_id):
            warn(
                f"Commande {model.id}: user {g.user.id} selected publisher_id="
                f"{model.publisher_id} but can_user_publish_for is False. "
            )
        if not model.publisher_id:
            if g.user.is_managing_another_bw:
                bw = get_selected_business_wall_for_user(g.user)
                if bw:
                    model.publisher_id = bw.organisation_id
            if not model.publisher_id and g.user.organisation_id:
                model.publisher_id = g.user.organisation_id


@register
def register_on_app(app: Flask) -> None:
    CommandesWipView.register(app)
