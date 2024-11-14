# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Work with "class Meta" attributes."""

from __future__ import annotations


def get_meta_attr(obj, attr: str, default=None):
    if not hasattr(obj, "Meta"):
        return default

    meta = obj.Meta
    if hasattr(meta, attr):
        return getattr(meta, attr)

    if hasattr(obj, "__class__"):
        cls = obj.__class__
    else:
        cls = obj

    for superclass in cls.mro():
        if (meta := getattr(superclass, "Meta", None)) and hasattr(meta, attr):
            return getattr(superclass.Meta, attr)

    return default


# Not sure we want this.
def get_label(obj) -> str:
    return get_meta_attr(obj, "type_label", "")
