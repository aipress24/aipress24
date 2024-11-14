# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import dramatiq
from blinker import ANY

from app.modules.search.backend import SearchBackend
from app.signals import document_created, document_updated

backend = SearchBackend()


@dramatiq.actor
def index_object(obj) -> None:
    backend.index_obj(obj)


@document_created.connect_via(ANY)
def on_document_created(sender, document, **kwargs):
    index_object.send(document)


@document_updated.connect_via(ANY)
def on_document_updated(sender, document, **kwargs):
    index_object.send(document)
