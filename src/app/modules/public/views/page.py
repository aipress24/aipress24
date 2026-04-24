# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

import toml
from flask import current_app, render_template
from markdown import markdown
from svcs.flask import container

from app.modules.public import get
from app.services.corporate_pages import CorporatePageService


@get("/page/<path:path>")
def page(path: str):
    path = path.removesuffix("/")

    # 1) DB — editable via the admin mini-CMS.
    # Only top-level slugs ; sub-paths keep the filesystem behaviour.
    if "/" not in path:
        svc = container.get(CorporatePageService)
        page_obj = svc.get(slug=path)
        if page_obj is not None:
            return _render_md_content(page_obj.title, page_obj.body_md)

    # 2) Filesystem fallback (legacy static-pages/ + rétrocompat pour
    # sub-paths éventuels).
    root = Path(current_app.root_path).parent.parent.parent / "static-pages"
    html_file = root / (path + ".html")
    md_file = root / (path + ".md")

    if html_file.exists():
        data = html_file.read_text()
        html = data.split("-->", 1)[1]
        title = "Some title"
        return render_template("pages/generic-page.j2", content=html, title=title)

    if md_file.exists():
        data = md_file.read_text()
        head, md = data.split("---", 1)
        head = head.strip()
        metadata = toml.loads(head)
        title = metadata.get("title", "Some title")
        return _render_md_content(title, md)

    return render_template("errors/404.j2"), 404


def _render_md_content(title: str, body_md: str):
    cls = "py-20 max-w-4xl mx-4 lg:mx-auto"
    html = f"""
        <div class="{cls}">
            <h1 class="text-3xl font-bold mb-6">{title}</h1>

            <div class="prose lg:prose-lg">
                {markdown(body_md)}
            </div>
        </div>
    """
    return render_template("pages/generic-page.j2", content=html, title=title)
