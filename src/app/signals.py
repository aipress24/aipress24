"""Application signal definitions for events and lifecycle hooks."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from blinker import signal

# Documents signals
document_created = signal("document-created")
document_updated = signal("document-updated")
article_published = signal("article-published")
article_unpublished = signal("article-unpublished")
article_updated = signal("article-updated")
communique_published = signal("communique-published")
communique_unpublished = signal("communique-unpublished")
communique_updated = signal("communique-updated")
event_published = signal("event-published")
event_unpublished = signal("event-unpublished")
event_updated = signal("event-updated")

# Initialisation signals
after_config = signal("after-config")
after_scan = signal("app-scan")
