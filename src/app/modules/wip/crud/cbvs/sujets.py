# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from flask import Flask, flash, g, redirect
from flask_super.registry import register

from app.flask.extensions import db
from app.flask.routing import url_for
from app.logging import warn
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import Sujet, SujetRepository
from app.modules.wip.services.sujet_notifications import (
    notify_media_of_sujet_proposition,
)

from ._base import BaseWipView
from ._forms import SujetForm
from ._table import BaseTable


class SujetsTable(BaseTable):
    id = "sujets-table"

    def __init__(self, q="") -> None:
        super().__init__(Sujet, q)

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

    def publish(self, id):
        """Bug 0132: move sujet DRAFT → PUBLIC and notify the target media."""
        repo = self._get_repo()
        sujet = cast("Sujet", self._get_model(id))

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
