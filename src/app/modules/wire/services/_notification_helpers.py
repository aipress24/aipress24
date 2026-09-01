# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ce que les notifications d'achat ont en commun.

`_extract_article_title` existait à l'identique dans
`gift_notification` et `cession_notification` (audit du 2026-09-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.wire.models import Post

#: Ce qui s'affiche quand la donnée manque. Le tiret cadratin des deux
#: notifieurs, à l'identique : ce n'est pas le moment de changer ce que
#: lisent les membres.
MISSING_LABEL = "—"


def article_title(post: Post) -> str:
    """Le titre de l'article, ou un marqueur visible.

    Un `Post` publié sans titre est une anomalie de données ; elle ne
    doit pas vider une notification de son sujet.
    """
    return post.title or MISSING_LABEL
