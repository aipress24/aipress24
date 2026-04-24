# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin — mini-CMS views.

Lists and edits the `CorporatePage` rows that back the public
`/page/<slug>` route. The public route falls back to the
`static-pages/*.md` files when a slug has no DB entry, so
un-migrated pages still render unchanged.

Spec: `local-notes/specs/corporate-pages-cms.md`.
"""

from __future__ import annotations

import re
from typing import cast

import bleach
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from markdown import markdown
from svcs.flask import container
from werkzeug import Response

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.models.auth import User
from app.modules.admin import blueprint
from app.modules.admin.cms import CorporatePageService

# Strips whole unsafe blocks (tag + content) before markdown sees them.
_UNSAFE_BLOCK_RE = re.compile(
    r"<(script|style|iframe|object|embed)\b[^>]*>.*?</\1\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)


@blueprint.route("/cms")
@nav(parent="index", icon="file-text", label="CMS")
def cms_list():
    """List all editable CMS pages (DB rows)."""
    svc = container.get(CorporatePageService)
    pages = sorted(svc.list_all(), key=lambda p: p.slug)
    return render_template(
        "admin/pages/cms_list.j2",
        title="CMS",
        pages=pages,
    )


@blueprint.route("/cms/<slug>/edit", methods=["GET", "POST"])
def cms_edit(slug: str) -> str | Response:
    """Edit a CMS page's title and body."""
    svc = container.get(CorporatePageService)
    page = svc.get(slug=slug)
    if page is None:
        flash(f"Page « {slug} » introuvable.", "error")
        return redirect(url_for("admin.cms_list"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body_md = request.form.get("body_md", "")
        user = cast(User, current_user)
        svc.upsert(
            slug=slug,
            title=title,
            body_md=body_md,
            updated_by=user if not user.is_anonymous else None,
        )
        db.session.commit()
        flash("Page enregistrée.", "success")
        return redirect(url_for("admin.cms_list"))

    return render_template(
        "admin/pages/cms_edit.j2",
        title=f"Éditer — {page.title or page.slug}",
        page=page,
    )


@blueprint.route("/cms/preview", methods=["POST"])
def cms_preview() -> str:
    """Render a Markdown preview for the inline editor."""
    body_md = request.form.get("body_md", "") or request.json.get("body_md", "")  # type: ignore[union-attr]
    # Strip dangerous tag+content blocks (script, style, iframe, object,
    # embed) before markdown so neither the tag nor its raw contents make
    # it into the preview.
    body_md = _UNSAFE_BLOCK_RE.sub("", body_md)
    rendered = markdown(body_md, extensions=["extra"])
    # Safety net: strip scripts / event handlers in case admin pastes something.
    safe_html = bleach.clean(
        rendered,
        tags=[
            *bleach.ALLOWED_TAGS,
            "p",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "pre",
            "table",
            "thead",
            "tbody",
            "tr",
            "th",
            "td",
            "hr",
            "br",
            "img",
            "span",
            "div",
        ],
        attributes={
            **bleach.ALLOWED_ATTRIBUTES,
            "img": ["src", "alt", "title"],
            "a": ["href", "title", "rel"],
            "span": ["class"],
            "div": ["class"],
        },
        strip=True,
    )
    return safe_html
