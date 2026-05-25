# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from attr import define
from flask import Flask, abort, flash, g, redirect
from flask_super.registry import register
from markupsafe import escape
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload
from werkzeug import Response

from app.flask.extensions import db
from app.flask.lib.templates import templated
from app.flask.routing import url_for
from app.logging import warn
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.bw.bw_activation.user_utils import (
    can_user_publish_for,
    get_selected_business_wall_for_user,
)
from app.modules.wip.models import Sujet, SujetRepository
from app.modules.wip.pr_access import user_can_access_newsroom
from app.modules.wip.services.sujet_notifications import (
    notify_media_of_sujet_proposition,
)

from ._base import BaseWipView
from ._forms import SujetForm
from ._table import BaseDataSource, BaseTable

# language=jinja2
# Bug #0132 (2026-05-14): the chief editor wants the author mention
# *at the very top* — between the "Voir le sujet '…'" heading and the
# form title — not below the form. We can't reorder the shared
# VIEW_TEMPLATE because Communiqué relies on `extra_view_html` staying
# *below* the form (bug #0128 image carousel). So Sujet gets its own
# view template that renders the author block first.
_SUJET_VIEW_TEMPLATE = """
{% extends "wip/layout/_base.j2" %}
{% block body_content %}
  {{ extra_view_html|safe }}
  {{ form_rendered|safe }}
{% endblock %}
"""


@define
class SujetDataSource(BaseDataSource):
    """Bug 0132: rédacteurs en chef of a target media must see PUBLIC sujets
    addressed to their organisation, not just sujets they own themselves.

    Without this override the default `M.owner == user` clause filtered out
    every sujet a journalist had just published to another media — the
    notification mail arrived but the sujet itself was invisible in the
    NEWSROOM list.
    """

    def _media_recipient_clause(self):
        user: User = g.user
        org_id = getattr(user, "organisation_id", None)
        if not org_id:
            return None
        M = self.model_class
        return and_(
            M.media_id == org_id,
            M.status == PublicationStatus.PUBLIC,
        )

    def _visibility_clause(self):
        M = self.model_class
        user: User = g.user
        own = M.owner_id == user.id
        media = self._media_recipient_clause()
        return or_(own, media) if media is not None else own

    def _base_query(self):
        M = self.model_class
        # Eager-load owner + media so the table renderer doesn't fire N+1
        # queries when reading author / media name on each row.
        stmt = (
            select(M)
            .options(selectinload(M.owner), selectinload(M.media))
            .where(self._visibility_clause())
            .where(M.deleted_at.is_(None))
        )
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


class SujetsTable(BaseTable):
    id = "sujets-table"

    def __init__(self, q="") -> None:
        super().__init__(Sujet, q)

    def get_columns(self):
        return [
            {
                "name": "titre",
                "label": "Titre",
                "class": "max-w-0 w-full truncate",
            },
            {
                "name": "owner",
                "label": "Auteur",
                "class": "max-w-24",
                "render": self.get_owner_name,
            },
            {
                "name": "status",
                "label": "Statut",
            },
            {
                "name": "created_at",
                "label": "Création",
            },
            {
                "name": "$actions",
                "label": "",
            },
        ]

    def get_owner_name(self, obj):
        owner = getattr(obj, "owner", None)
        if not owner:
            return ""
        return owner.full_name

    def _make_datasource(self, model_class: type, q: str) -> BaseDataSource:
        return SujetDataSource(model_class=model_class, q=q)

    def url_for(self, obj, _action="get", **kwargs):  # type: ignore[override]
        return url_for(f"SujetsWipView:{_action}", id=obj.id, **kwargs)

    def get_actions(self, item):
        """Bug 0132: surface Publier/Dépublier so journalists can actually
        send their sujet to the targeted media — without a Publier action,
        the sujet sat as DRAFT and no one ever received it."""
        actions = [
            {"label": "Voir", "url": self.url_for(item)},
            {"label": "Modifier", "url": self.url_for(item, "edit")},
        ]
        if item.status == PublicationStatus.DRAFT:
            actions.append({"label": "Publier", "url": self.url_for(item, "publish")})
        else:
            actions.append(
                {"label": "Dépublier", "url": self.url_for(item, "unpublish")}
            )
        actions.append({"label": "Supprimer", "url": self.url_for(item, "delete")})
        return actions


class SujetsWipView(BaseWipView):
    name = "sujets"

    model_class = Sujet
    repo_class = SujetRepository
    table_class = SujetsTable
    form_class = SujetForm
    doc_type = "sujet"

    route_base = "sujets"
    path = "/wip/sujets/"

    # UI
    icon = "newspaper"

    label_main = "Newsroom: sujets"
    label_list = "Liste des sujets"
    label_new = "Créer un sujet"
    label_edit = "Modifier le sujet"
    label_view = "Voir le sujet"

    table_id = "sujet-table-body"

    msg_delete_ok = "Le sujet a été supprimé"
    msg_delete_ko = "Vous n'êtes pas autorisé à supprimer ce sujet"

    def _post_update_model(self, model: Sujet) -> None:
        # Validate publisher_id: if the user selected a client org they are
        # not authorized to publish for, warn but DO NOT silently reset.
        # The publish() step will enforce the auth and show an explicit error.
        if model.publisher_id and not can_user_publish_for(g.user, model.publisher_id):
            warn(
                f"Sujet {model.id}: user {g.user.id} selected publisher_id="
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

    def before_request(self, *_args, **_kwargs) -> Response | None:
        if resp := super().before_request(*_args, **_kwargs):
            return resp

        if not user_can_access_newsroom(g.user):
            abort(403)
        return None

    @templated(_SUJET_VIEW_TEMPLATE)
    def get(self, id):
        """Bug #0132 (2026-05-14): render the author mention at the top
        of the developed sujet, before the form, using Sujet's own
        view template (see `_SUJET_VIEW_TEMPLATE`)."""
        model = self._get_model(id)
        title = f"{self.label_view} '{model.title}'"
        return self._view_ctx(model, title=title, mode="view")

    def _extra_view_html(self, model, mode: str) -> str:
        """Show the author — name, fonction and média — above the form.

        Bug #0132: the chief editor of the receiving media opens the
        developed sujet (view or edit mode) and must see who proposed
        it, with enough context to identify them, but cannot modify the
        author. Per the 2026-05-14 feedback the line reads
        "Auteur : <nom>, <fonction>, <média>" and sits at the top.

        Rendered via `{{ extra_view_html|safe }}`, so every
        user-controlled value must be HTML-escaped before interpolation.
        """
        if mode == "new":
            return ""
        owner = getattr(model, "owner", None) if model else None
        if not owner:
            return ""

        publisher = getattr(model, "publisher", None)
        org_name = publisher.name if publisher else owner.organisation_name

        parts = [owner.full_name, owner.job_title, org_name]
        line = ", ".join(escape(p) for p in parts if p)
        return f"""
        <div class="mb-6 border-l-4 border-blue-400 bg-blue-50 p-4">
            <h3 class="text-sm font-medium text-gray-500">Auteur</h3>
            <p class="text-sm font-medium text-gray-900">{line}</p>
        </div>
        """

    def publish(self, id):
        """Bug 0132: move sujet DRAFT → PUBLIC and notify the target media."""
        repo = self._get_repo()
        sujet = cast("Sujet", self._get_model(id))

        publisher_id = sujet.publisher_id or g.user.organisation_id or None
        if publisher_id and not can_user_publish_for(g.user, publisher_id):
            flash(
                "Vous n'êtes pas autorisé à publier pour cette organisation.",
                "error",
            )
            return redirect(self._url_for("edit", id=id))

        try:
            sujet.publish()
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("edit", id=id))

        repo.update(sujet, auto_commit=False)
        db.session.commit()

        media_org = getattr(sujet, "media", None)
        if media_org is not None:
            try:
                notify_media_of_sujet_proposition(
                    author=g.user,
                    media_org=media_org,
                    sujet_title=sujet.titre,
                    sujet_url=_absolute_url_for("SujetsWipView:get", id=sujet.id),
                )
            except Exception as exc:  # never block the publish on a mail issue
                warn(f"Sujet proposition notif failed (sujet {sujet.id}): {exc}")

        flash("Le sujet a été publié et envoyé au média sélectionné.")
        return redirect(self._url_for("index"))

    def unpublish(self, id):
        repo = self._get_repo()
        sujet = cast("Sujet", self._get_model(id))
        try:
            sujet.unpublish()
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("get", id=id))
        repo.update(sujet, auto_commit=False)
        db.session.commit()
        flash("Le sujet a été dépublié")
        return redirect(self._url_for("index"))


def _absolute_url_for(endpoint: str, **values) -> str:
    """Build an absolute URL for the notification's link."""
    from flask import current_app, url_for as _url_for

    domain = str(current_app.config.get("SERVER_NAME") or "aipress24.com")
    protocol = "http" if domain.startswith("127.") else "https"
    path = _url_for(endpoint, **values)
    return f"{protocol}://{domain}{path}"


@register
def register_on_app(app: Flask) -> None:
    SujetsWipView.register(app)
