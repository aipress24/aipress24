# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from functools import singledispatch

from flask import url_for as url_for_orig

from app.flask.lib.view_model import ViewModel


@singledispatch
def url_for(obj, _ns: str = "", **_kw):
    if hasattr(obj, "_url"):
        return obj._url
    msg = f"Illegal argument for 'url_for': {obj} (type: {type(obj)})"
    raise RuntimeError(msg)


@url_for.register
def url_for_vm(obj: ViewModel, _ns: str = "", **_kw):
    return url_for(obj._unwrap())


@url_for.register
def url_for_str(name: str, _ns: str = "", **kw) -> str:
    return url_for_orig(name, **kw)


@url_for.register
def url_for_dict(d: dict, _ns: str = "", **_kw) -> str:
    if "_url" in d:
        return d["_url"]
    msg = f"Illegal argument for 'url_for': {d} (type: {type(d)})"
    raise RuntimeError(msg)


# TEMP
@url_for.register
def url_for_none(_none: None, _ns: str = "", **_kw) -> str:
    return "#NONE"
