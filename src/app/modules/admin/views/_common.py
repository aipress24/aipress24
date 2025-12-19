# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared helpers for admin views."""

from __future__ import annotations

from urllib.parse import urlencode

from flask import Response, request, url_for


def build_url(endpoint: str, offset: int = 0, search: str = "") -> str:
    """Build URL with pagination query parameters."""
    params: dict[str, int | str] = {}
    if offset > 0:
        params["offset"] = offset
    if search:
        params["search"] = search
    base_url = url_for(endpoint)
    if params:
        return f"{base_url}?{urlencode(params)}"
    return base_url


def build_table_context(ds_class, table_class):
    """Build context for table pages."""
    ds = ds_class()
    records = ds.records()
    table = table_class(records)
    table.start = ds.offset + 1
    count = ds.count()
    table.end = min(ds.offset + ds.limit, count)
    table.count = count
    table.searching = ds.search
    return {"table": table, "ds": ds}


def handle_table_post(ds_class, endpoint: str) -> Response:
    """Handle POST for table pages (pagination/search)."""
    ds = ds_class()
    action = request.form.get("action")
    search_string = request.form.get("search", "")

    if action == "next":
        redirect_url = build_url(endpoint, offset=ds.next_offset(), search=ds.search)
    elif action == "previous":
        redirect_url = build_url(endpoint, offset=ds.prev_offset(), search=ds.search)
    elif search_string:
        offset = 0 if search_string != ds.search else ds.offset
        redirect_url = build_url(endpoint, offset=offset, search=search_string)
    else:
        redirect_url = build_url(endpoint)

    response = Response("")
    response.headers["HX-Redirect"] = redirect_url
    return response
