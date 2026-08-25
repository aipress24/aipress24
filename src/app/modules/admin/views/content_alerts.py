# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin view to moderate reported content alerts."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass

import sqlalchemy as sa
from arrow import now
from flask import flash, redirect, render_template, url_for
from werkzeug.exceptions import NotFound

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.models.content_alert import ContentAlert
from app.models.lifecycle import PublicationStatus
from app.modules.admin import blueprint
from app.modules.wip.models.comroom.communique import Communique
from app.modules.wip.models.newsroom.article import Article
from app.modules.wire.models import ArticlePost, Post, PressReleasePost
from app.signals import article_unpublished, communique_unpublished


@dataclass
class AlertViewModel:
    alert: ContentAlert
    post_is_deleted: bool
    post_exists: bool
    post_url: str
    created_at_str: str


@blueprint.route("/content-alerts")
@nav(
    parent="index",
    icon="alert-triangle",
    label="Signalements",
)
def content_alerts():
    """List all reported content alerts."""
    stmt = sa.select(ContentAlert).order_by(ContentAlert.created_at.desc())
    alerts = list(db.session.scalars(stmt))

    post_ids = {a.post_id for a in alerts if a.post_id}
    posts_by_id: dict[int, Post] = {}
    if post_ids:
        post_stmt = sa.select(Post).where(Post.id.in_(post_ids))
        posts_by_id = {p.id: p for p in db.session.scalars(post_stmt)}

    items: list[AlertViewModel] = []
    for alert in alerts:
        post = posts_by_id.get(alert.post_id)
        post_exists = post is not None
        if post_exists:
            post_is_deleted = post.deleted_at is not None
        else:
            post_is_deleted = True
        post_url = alert.post_url
        if not post_url and post_exists:
            with contextlib.suppress(Exception):
                post_url = url_for(post, _external=True)

        created_dt = alert.created_at
        created_at_str = (
            created_dt.strftime("%d/%m/%Y à %H:%M")
            if hasattr(created_dt, "strftime")
            else str(created_dt or "")
        )

        items.append(
            AlertViewModel(
                alert=alert,
                post_is_deleted=post_is_deleted,
                post_exists=post_exists,
                post_url=post_url,
                created_at_str=created_at_str,
            )
        )

    return render_template(
        "admin/pages/content_alerts.j2",
        items=items,
        title="Signalements de contenu",
    )


@blueprint.route("/content-alerts/<int:alert_id>/delete-post", methods=["POST"])
def delete_reported_post(alert_id: int):
    """Delete the post associated with a content alert."""
    alert = db.session.get(ContentAlert, alert_id)
    if alert is None:
        raise NotFound

    post_id = alert.post_id
    post = db.session.get(Post, post_id)

    article: Article | None = None
    communique: Communique | None = None

    if isinstance(post, ArticlePost) and post.newsroom_id:
        article = db.session.get(Article, post.newsroom_id)
    elif isinstance(post, PressReleasePost) and post.newsroom_id:
        communique = db.session.get(Communique, post.newsroom_id)

    current_time = now(LOCAL_TZ)

    if post is not None:
        post.deleted_at = current_time
        post.status = PublicationStatus.DRAFT

    if article is not None:
        article.deleted_at = current_time
        with contextlib.suppress(Exception):
            article_unpublished.send(article)
    elif communique is not None:
        communique.deleted_at = current_time
        with contextlib.suppress(Exception):
            communique_unpublished.send(communique)

    # Mark alert as resolved
    alert.is_resolved = True
    alert.resolved_at = current_time

    db.session.commit()

    title = alert.post_title or (post.title if post else f"#{post_id}")
    flash(f"Le contenu « {title} » a été supprimé.", "success")
    return redirect(url_for(".content_alerts"))
