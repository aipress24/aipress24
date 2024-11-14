# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Response, render_template

from app.flask.routing import url_for
from app.flask.sqla import get_multi
from app.models.content.textual import Article

from .. import blueprint


@blueprint.route("/sitemap.xml")
def sitemap():
    # stmt = (
    #     select(Article)
    #     # .where(JobPost.status.in_([STATUS.PUBLIC, STATUS.EXPIRED]))
    #     # .order_by(JobPost.id.desc())
    # )
    articles = get_multi(Article)

    urls = []
    for article in articles:
        # TODO: change 'private' to 'public'
        url = {
            "loc": url_for(article, _external=True),
            "lastmod": article.modified_at.strftime("%Y-%m-%d"),
            "changefreq": "daily",
        }
        urls.append(url)

    body = render_template("pages/sitemap.j2", urls=urls)
    return Response(body, mimetype="text/xml")
