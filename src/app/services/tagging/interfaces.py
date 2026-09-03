# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations


class Taggable:
    """Marker: this model accepts tags.

    Must stay empty. `ArticlePost` and `PressReleasePost` inherit it
    among their declarative bases, so any annotation here — `id: int`,
    say — becomes a column SQLAlchemy tries to map, and importing the
    models fails.
    """
