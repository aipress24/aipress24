# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin view to moderate reported content alerts."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import NamedTuple

import sqlalchemy as sa
from arrow import now
from flask import flash, redirect, render_template
from werkzeug.exceptions import NotFound

from app.constants import CONTENT_ALERTS_RETENTION_DAYS, LOCAL_TZ
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.models.base_content import BaseContent
from app.models.comment import Comment
from app.models.content_alert import ContentAlert
from app.models.lifecycle import PublicationStatus
from app.modules.admin import blueprint
from app.modules.wip.models.comroom.communique import Communique
from app.modules.wip.models.newsroom.article import Article
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.services.comments import delete_comment
from app.signals import article_unpublished, communique_unpublished


class AlertDetail(NamedTuple):
    alert: ContentAlert
    created_at_str: str


@dataclass
class AlertViewModel:
    alert: ContentAlert
    post_is_deleted: bool
    post_exists: bool
    post_url: str
    created_at_str: str
    alerts: list[AlertDetail]
    is_resolved: bool = False


def _format_datetime(dt: object) -> str:
    strftime = getattr(dt, "strftime", None)
    if callable(strftime):
        return str(strftime("%d/%m/%Y à %H:%M"))
    return str(dt or "")


def _resolve_post_url(group: list[ContentAlert], post: BaseContent | None) -> str:
    for alert in group:
        if alert.post_url:
            return alert.post_url
    if post is not None:
        with contextlib.suppress(Exception):
            return url_for(post, _external=True)
    return ""


def _build_alert_vm(
    group: list[ContentAlert],
    post: BaseContent | None,
) -> AlertViewModel:
    latest_alert = group[0]
    post_exists = post is not None
    if post_exists:
        post_is_deleted = bool(getattr(post, "deleted_at", None))
    else:
        post_is_deleted = True
    post_url = _resolve_post_url(group, post)

    alert_details = [
        AlertDetail(alert=a, created_at_str=_format_datetime(a.created_at))
        for a in group
    ]

    is_resolved = all(a.is_resolved for a in group)

    return AlertViewModel(
        alert=latest_alert,
        post_is_deleted=post_is_deleted,
        post_exists=post_exists,
        post_url=post_url,
        created_at_str=_format_datetime(latest_alert.created_at),
        alerts=alert_details,
        is_resolved=is_resolved,
    )


@blueprint.route("/content-alerts")
@nav(
    parent="index",
    icon="alert-triangle",
    label="Signalements",
)
def content_alerts():
    """List reported content alerts from the last 90 days."""
    cutoff = now(LOCAL_TZ).shift(days=-CONTENT_ALERTS_RETENTION_DAYS)
    stmt = (
        sa.select(ContentAlert)
        .where(ContentAlert.created_at >= cutoff)
        .order_by(ContentAlert.created_at.desc())
    )
    alerts = list(db.session.scalars(stmt))

    post_ids = {int(a.post_id) for a in alerts if a.post_id}
    posts_by_id: dict[int, BaseContent] = {}
    if post_ids:
        post_stmt = sa.select(BaseContent).where(BaseContent.id.in_(post_ids))
        posts_by_id = {p.id: p for p in db.session.scalars(post_stmt)}

    # Group alerts by post_id
    grouped_alerts: dict[int, list[ContentAlert]] = {}
    for alert in alerts:
        post_id = int(alert.post_id)
        grouped_alerts.setdefault(post_id, []).append(alert)

    items = [
        _build_alert_vm(group, posts_by_id.get(post_id))
        for post_id, group in grouped_alerts.items()
    ]

    return render_template(
        "admin/pages/content_alerts.j2",
        items=items,
        title="Signalements de contenu",
        CONTENT_ALERTS_RETENTION_DAYS=CONTENT_ALERTS_RETENTION_DAYS,
    )


@blueprint.route("/content-alerts/<int:alert_id>/dismiss", methods=["POST"])
def dismiss_content_alert(alert_id: int):
    """Dismiss a content alert (mark resolved without deleting the content)."""
    alert = db.session.get(ContentAlert, alert_id)
    if alert is None:
        raise NotFound

    post_id = alert.post_id
    current_time = now(LOCAL_TZ)

    # Mark alert as resolved
    alert.is_resolved = True
    alert.resolved_at = current_time

    # Mark all other alerts for this post as resolved
    if post_id:
        stmt = sa.select(ContentAlert).where(
            ContentAlert.post_id == post_id,
            ContentAlert.is_resolved.is_(False),
        )
        for other_alert in db.session.scalars(stmt):
            other_alert.is_resolved = True
            other_alert.resolved_at = current_time

    db.session.commit()

    post = db.session.get(BaseContent, post_id) if post_id else None
    title = alert.post_title or (
        getattr(post, "title", None) if post else f"#{post_id}"
    )
    flash(
        f"Le signalement concernant « {title} » a été classé sans suite.",
        "success",
    )
    return redirect(url_for(".content_alerts"))


@blueprint.route("/content-alerts/<int:alert_id>/delete-post", methods=["POST"])
def delete_reported_post(alert_id: int):
    """Delete the post associated with a content alert."""
    alert = db.session.get(ContentAlert, alert_id)
    if alert is None:
        raise NotFound

    post_id = alert.post_id
    post = db.session.get(BaseContent, post_id)

    article: Article | None = None
    communique: Communique | None = None

    if isinstance(post, ArticlePost) and post.newsroom_id:
        article = db.session.get(Article, post.newsroom_id)
    elif isinstance(post, PressReleasePost) and post.newsroom_id:
        communique = db.session.get(Communique, post.newsroom_id)

    current_time = now(LOCAL_TZ)

    if post is not None:
        if isinstance(post, Comment):
            delete_comment(post, deleted_at=current_time)
        else:
            post.deleted_at = current_time
            if hasattr(post, "status"):
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

    # Mark all other alerts for this post as resolved
    if post_id:
        stmt = sa.select(ContentAlert).where(
            ContentAlert.post_id == post_id,
            ContentAlert.is_resolved.is_(False),
        )
        for other_alert in db.session.scalars(stmt):
            other_alert.is_resolved = True
            other_alert.resolved_at = current_time

    db.session.commit()

    title = alert.post_title or (
        getattr(post, "title", None) if post else f"#{post_id}"
    )
    flash(f"Le contenu « {title} » a été supprimé.", "success")
    return redirect(url_for(".content_alerts"))
