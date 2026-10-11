# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The image editor template shared by articles, communiqués and events."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from flask import url_for

if TYPE_CHECKING:
    from flask import Flask


def _image(image_id: int, position: int) -> SimpleNamespace:
    return SimpleNamespace(
        id=image_id,
        position=position,
        url=f"https://example.com/{image_id}.png",
        caption=f"Légende {image_id}",
        copyright="",
        is_first=position == 0,
        is_last=position == 1,
    )


@pytest.mark.parametrize(
    ("view", "id_param", "prefix", "back_label"),
    [
        ("ArticlesWipView", "article_id", "/wip/articles", "Retour aux articles"),
        (
            "CommuniquesWipView",
            "communique_id",
            "/wip/communiques",
            "Retour aux communiqués",
        ),
        ("EventsWipView", "event_id", "/wip/events", "Retour aux événements"),
    ],
)
def test_each_content_type_gets_its_own_image_routes(
    app: Flask, view: str, id_param: str, prefix: str, back_label: str
) -> None:
    content = SimpleNamespace(id=42, sorted_images=[_image(7, 0), _image(8, 1)])

    with app.test_request_context("/"):
        # The body block alone: the page layout needs the whole app
        # context, which says nothing about the image routes.
        template = app.jinja_env.get_template("wip/_images.j2")
        context = template.new_context(
            {
                "url_for": url_for,
                "content": content,
                "view": view,
                "id_param": id_param,
                "back_label": back_label,
            }
        )
        html = "".join(template.blocks["body_content"](context))

    assert f"{prefix}/42/images/7/delete" in html
    assert f"{prefix}/42/images/8/move" in html
    assert back_label in html
