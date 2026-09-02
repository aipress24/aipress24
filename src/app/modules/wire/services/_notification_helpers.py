# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""What the purchase notifications have in common.

`_extract_article_title` existed identically in `gift_notification` and
`cession_notification` (audit 2026-09-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.wire.models import Post

#: What is displayed when the data is missing. The em dash both
#: notifiers used, unchanged: this is not the moment to alter what
#: members read.
MISSING_LABEL = "—"


def article_title(post: Post) -> str:
    """The article's title, or a visible marker.

    A `Post` published without a title is a data anomaly; it must not
    strip a notification of its subject.
    """
    return post.title or MISSING_LABEL
