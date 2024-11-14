# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations


def merge_dicts(target: dict, other: dict) -> dict:
    """Recursive dict merge. Inspired by :meth:``dict.update()``, instead of
    updating only top-level keys, dict_merge recurses down into dicts nested to
    an arbitrary depth, updating keys. The ``other`` is merged into ``target``.

    :param target: dict onto which the merge is executed
    :param other: dict merged into target
    :return: the target dict (NOT a copy!)
    """
    for k, v in other.items():
        if k in target and isinstance(target[k], dict) and isinstance(v, dict):
            merge_dicts(target[k], v)
        else:
            target[k] = v

    return target
