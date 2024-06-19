# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from blinker import signal

# Documents signals
document_created = signal("document-created")
document_updated = signal("document-updated")
article_published = signal("article-published")
article_unpublished = signal("article-unpublished")

# Initialisation signals
after_config = signal("after-config")
after_scan = signal("app-scan")
