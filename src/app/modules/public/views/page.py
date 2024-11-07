# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

import toml
from flask import current_app, render_template
from markdown import markdown

from .. import blueprint


@blueprint.route("/page/<path:path>")
def page(path: str):
    path = path.removesuffix("/")

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
        cls = "py-20 max-w-5xl mx-auto prose lg:prose-lg xl:prose-xl"
        html = f"""
            <div class="{cls}">
                <h1>{title}</h1>
                {markdown(md)}
            </div>
        """
        title = "Some title"
        return render_template("pages/generic-page.j2", content=html, title=title)

    return render_template("pages/404.j2"), 404
