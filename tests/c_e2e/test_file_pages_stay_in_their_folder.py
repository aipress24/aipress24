# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`/sandbox/<path>` and `/page/<path>` serve files from one folder each."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from app.modules.public.views.sandbox import TEMPLATE_DIR

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient

# A tracked page outside both folders, with the `-->` `/page` splits on.
OUTSIDE = Path(
    "src/app/modules/bw/bw_activation/templates/bw_activation/"
    "00_confirm_subscription.html"
).resolve()


def _escape(folder: Path) -> str:
    """The URL path from `folder` to `OUTSIDE`, slashes percent-encoded."""
    relative = os.path.relpath(OUTSIDE.with_suffix(""), folder)
    return relative.replace("/", "%2F")


def test_sandbox_serves_its_own_pages(client: FlaskClient) -> None:
    assert client.get("/sandbox/bw-edit").status_code == 200


def test_sandbox_refuses_a_path_out_of_its_folder(client: FlaskClient) -> None:
    response = client.get(f"/sandbox/{_escape(TEMPLATE_DIR)}")

    assert response.status_code == 404


@pytest.mark.parametrize("encode", [True, False])
def test_page_refuses_a_path_out_of_its_folder(
    app: Flask, client: FlaskClient, encode: bool
) -> None:
    root = Path(app.root_path).parent.parent.parent / "static-pages"
    path = _escape(root)
    if not encode:
        path = path.replace("%2F", "/")

    response = client.get(f"/page/{path}")

    assert response.status_code == 404
