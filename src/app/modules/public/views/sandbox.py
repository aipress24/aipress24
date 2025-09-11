# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from werkzeug.exceptions import NotFound

from app.modules.public import get

TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "sandbox-pages"


@get("/sandbox/")
def sandbox_index():
    # List all HTML files
    html_files = []
    if TEMPLATE_DIR.exists():
        for file_path in TEMPLATE_DIR.glob("*.html"):
            # Get the name without extension
            name = file_path.stem
            html_files.append(name)

    # Sort the files alphabetically
    html_files.sort()

    # Generate HTML with links
    html_content = "<html><head><title>Sandbox Pages</title></head><body>"
    html_content += "<h1>Sandbox Pages</h1>"
    html_content += "<ul>"

    for file_name in html_files:
        html_content += f'<li><a href="/sandbox/{file_name}">{file_name}</a></li>'

    html_content += "</ul>"
    html_content += "</body></html>"

    return html_content


@get("/sandbox/<path:path>")
def sandbox(path: str):
    path = path.removesuffix("/")

    html_file = TEMPLATE_DIR / (path + ".html")

    if not html_file.exists():
        msg = "File not found"
        raise NotFound(msg)

    return html_file.read_text()
