# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from attr import define
from flask import Flask, flash, g, redirect
from flask_super.registry import register
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload
from werkzeug import Response
from werkzeug.exceptions import Forbidden, NotFound

from app.flask.extensions import db
from app.flask.lib.templates import templated
from app.flask.routing import url_for
from app.logging import report_failure, warn
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.bw.bw_activation.user_utils import (
    can_user_publish_for,
    get_selected_business_wall_for_user,
)
from app.modules.wip.models import Sujet, SujetRepository
from app.modules.wip.pr_access import (
    user_can_access_comroom,
    user_can_access_newsroom,
)
from app.modules.wip.services.newsroom.sujet_accept import (
    accept_sujet_as_commande,
    notify_author_of_sujet_acceptance,
)
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


_REDAC_CHEF_PROFILES = frozenset({"PM_DIR", "PM_DIR_INST", "PM_DIR_SYND"})


def _is_redac_chef_of_org(user, org_id) -> bool:
    """Bug #0132 pt 1 (Erick, 2026-06-02) : Sujets received by a media
    must only surface for actual rédacteurs en chef, not for every
    journalist at the same org.

    A user qualifies as rédac chef if either :
    - their KYC profile is one of the `PM_DIR*` codes (Directeur de
      la rédaction, Directeur institutionnel, Directeur syndicat) ;
    - they hold an ACCEPTED BWMi or BW_OWNER RoleAssignment on the
      media's active BW (the org-management equivalent).
    """
    if user is None or getattr(user, "is_anonymous", False):
        return False
    profile = getattr(user, "profile", None)
    if profile is not None:
        profile_code = getattr(profile, "profile_code", "") or ""
        if profile_code in _REDAC_CHEF_PROFILES:
            return True

    # Lazy imports to keep this module importable without pulling
    # the full BW activation tree during cold start.
    from app.modules.bw.bw_activation.models import (
        BusinessWall,
        BWRoleType,
        InvitationStatus,
    )
    from app.modules.bw.bw_activation.models.business_wall import BWStatus

    bw = db.session.scalars(
        select(BusinessWall).where(
            BusinessWall.organisation_id == org_id,
            BusinessWall.status == BWStatus.ACTIVE.value,
        )
    ).first()
    if bw is None:
        return False
    user_id = getattr(user, "id", None)
    if user_id is None:
        return False
    elevated_roles = {BWRoleType.BWMI.value, BWRoleType.BW_OWNER.value}
    for assignment in bw.role_assignments:
        if (
            assignment.user_id == user_id
            and assignment.invitation_status == InvitationStatus.ACCEPTED.value
            and assignment.role_type in elevated_roles
        ):
            return True
    return False


@define
class SujetDataSource(BaseDataSource):
    """Bug 0132: rédacteurs en chef of a target media must see PUBLIC sujets
    addressed to their organisation, not just sujets they own themselves.

    Without this override the default `M.owner == user` clause filtered out
    every sujet a journalist had just published to another media — the
    notification mail arrived but the sujet itself was invisible in the
    NEWSROOM list.

    Part 1 (#0132 pt 1, Erick 2026-06-02) : the « received » side of
    the clause now also requires the viewer to be a rédac chef of the
    target media — ordinary journalists at the same org no longer see
    the proposal, which restores the targeting Nicolas relies on.
    """

    def _media_recipient_clause(self):
        user: User = g.user
        org_id = getattr(user, "organisation_id", None)
        if not org_id:
            return None
        # Bug #0132 pt 1 — gate the received-Sujet view on a rédac
        # chef qualification.
        if not _is_redac_chef_of_org(user, org_id):
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
        the sujet sat as DRAFT and no one ever received it.

        Ticket #0132 part 3 : also surface « Accepter » for the rédac
        chef receiving a PUBLIC sujet (= member of the target media's
        org). Acceptance materialises a Commande and notifies the author.
        """
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
        # Accepter : only on PUBLIC sujets, and only for the rédac chef
        # (member of the target media). The route enforces the same
        # guard server-side ; we just hide the action when it wouldn't
        # apply, to keep the menu honest.
        # `g.user` may not be set in some unit tests that call
        # `get_actions` directly without a Flask request context —
        # tolerate that gracefully (the action is then suppressed).
        current_user = getattr(g, "user", None)
        user_org_id = getattr(current_user, "organisation_id", None)
        if (
            item.status == PublicationStatus.PUBLIC
            and user_org_id is not None
            and user_org_id == item.media_id
        ):
            actions.append({"label": "Accepter", "url": self.url_for(item, "accept")})
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

    def _get_model(self, id):
        """Per-record visibility gate for Sujet (security VULN-001).

        The LIST view's `_media_recipient_clause` restricts received
        Sujets to rédacteurs en chef (#0132 pt 1). The same gate must
        apply when a record is fetched by primary key — otherwise the
        get / edit / accept / publish / unpublish / delete routes
        bypass the visibility rule via direct URL.

        Authorized viewers :
        - the Sujet's own owner, regardless of status ;
        - the target media's rédac chef when the Sujet is PUBLIC.

        Anything else 404s (existence-hiding).
        """
        model = super()._get_model(id)
        if model is None or self._user_can_access_sujet(model):
            return model
        raise NotFound

    def _user_can_access_sujet(self, sujet: Sujet) -> bool:
        user = g.user
        if user is None or user.is_anonymous:
            return False
        if sujet.owner_id == user.id:
            return True
        return (
            sujet.media_id == user.organisation_id
            and sujet.status == PublicationStatus.PUBLIC
            and _is_redac_chef_of_org(user, sujet.media_id)
        )

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

        # Bug #0177 (Erick, 2026-06-02) : Sujets reste accessible aux
        # journalistes (via Newsroom) ET aux attachés de presse via
        # Com'room — Newsroom est exclusivement journalistique mais
        # le Sujet en tant qu'objet métier reste pertinent pour les
        # deux communautés.
        if not (user_can_access_newsroom(g.user) or user_can_access_comroom(g.user)):
            raise Forbidden
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
        """Render the author mini-card above the form.

        Bug #0132 part 2 (Erick, 2026-06-02) : the previous version
        rendered a text-only blue box (« Auteur : <nom>, <fonction>,
        <média> »). Erick : « on ne voit toujours pas la carte
        résumée du journaliste avec sa photo ». Replace with the
        shared `poster_card` macro (photo + name + role +
        organisation + profile link + BW link).
        """
        if mode == "new":
            return ""
        owner = getattr(model, "owner", None) if model else None
        if not owner:
            return ""

        from flask import render_template

        return render_template(
            "wip/fragments/sujet_author_card.j2",
            author=owner,
        )

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
                report_failure(
                    f"Sujet proposition notif failed (sujet {sujet.id})", exc
                )

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

    def accept(self, id):
        """Bug #0132 part 3 : materialise a Commande from the sujet,
        archive the sujet, notify the author (bell + mail #0132 part
        6)."""
        sujet = cast("Sujet", self._get_model(id))
        try:
            commande = accept_sujet_as_commande(sujet, g.user)
        except ValueError as e:
            flash(str(e), "error")
            return redirect(self._url_for("get", id=id))
        db.session.commit()

        author = getattr(sujet, "owner", None)
        if author is not None:
            commande_url = _absolute_url_for("CommandesWipView:get", id=commande.id)
            notify_author_of_sujet_acceptance(
                author=author,
                accepter=g.user,
                sujet_title=sujet.titre,
                commande_url=commande_url,
            )
            # Bug #0132 part 6 (Erick, 2026-06-02) : in addition to
            # the bell notification, send an email so the journalist
            # learns about the acceptance even if they don't open
            # AiPRESS24 right away. Mail failures must not undo the
            # state change — wrap in try/except.
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
        flash("Sujet accepté : une commande a été créée et l'auteur a été notifié.")
        return redirect(url_for("CommandesWipView:index"))


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
