# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import contextlib
from functools import singledispatchmethod
from typing import Any

import typesense
from attr import frozen
from flask import current_app
from loguru import logger
from typesense.collection import Collection
from typesense.exceptions import ObjectNotFound

from app.flask.routing import url_for
from app.models.auth import User
from app.models.content import Article, PressRelease
from app.services.tagging import get_tags

from .constants import COLLECTIONS

CLASSES = {
    "articles": Article,
    "press-releases": PressRelease,
}

DEFAULT_FIELDS = [
    {"name": "title", "type": "string"},
    {"name": "text", "type": "string"},
    {"name": "summary", "type": "string"},
    {"name": "author", "type": "string"},
    {"name": "timestamp", "type": "int64"},
    {"name": "tags", "type": "string[]", "facet": True},
    {"name": "url", "type": "string"},
]

SCHEMAS = [
    {
        "name": coll["name"],
        "fields": DEFAULT_FIELDS,
        # "default_sorting_field": "ratings",
    }
    for coll in COLLECTIONS
]


@frozen
class SearchBackend:
    debug: bool = False

    @staticmethod
    def get_client() -> typesense.Client:
        host = current_app.config["TYPESENSE_HOST"]
        port = current_app.config.get("TYPESENSE_PORT", 8108)
        api_key = current_app.config["TYPESENSE_API_KEY"]
        nodes = [{"host": host, "port": port, "protocol": "http"}]
        return typesense.Client({
            "nodes": nodes,
            "api_key": api_key,
        })

    def get_collection(self, name) -> Collection:
        client = self.get_client()
        with contextlib.suppress(ObjectNotFound):
            if collection := client.collections[name]:
                return collection
        msg = f"Unknown collection: {name}"
        raise ValueError(msg)

    def make_schema(self) -> None:
        client = self.get_client()
        for schema in SCHEMAS:
            name = schema["name"]

            with contextlib.suppress(ObjectNotFound):
                collection = self.get_collection(name)
                collection.delete()
                logger.info("Deleted collection: {}", name)

            client.collections.create(schema)
            logger.info("Created collection: {}", name)

    def index_all(self) -> None:
        for name, cls in self._get_collections():
            logger.info("Indexing collection: {}", name)
            docs = []
            for obj in cls.query.all():
                d = self.adapt(obj)
                docs.append(d)
            if docs:
                collection = self.get_collection(name)
                collection.documents.import_(docs)

    def index_obj(self, obj) -> None:
        name = self._get_collection_name_for(obj)
        d = self.adapt(obj)
        self.get_collection(name).documents.upsert(d)

    @staticmethod
    def _get_collections():
        for collection in COLLECTIONS:
            name = collection["name"]
            cls = collection["class"]
            if not cls:
                continue
            yield name, cls

    @staticmethod
    def _get_collection_name_for(obj) -> str:
        for collection in COLLECTIONS:
            name = collection["name"]
            cls = collection["class"]
            if not cls:
                continue
            if isinstance(obj, cls):
                return name
        msg = f"Unknown collection for {obj}"
        raise ValueError(msg)

    @staticmethod
    def _adapt(obj):
        def _get_attr(o, *attrs, default: str = "") -> Any:
            for attr in attrs:
                if (value := getattr(o, attr, None)) is not None:
                    return value

            return default

        def _get_timestamp(obj):
            pub_date = _get_attr(obj, "published_at", "created_at")
            if pub_date:
                return int(pub_date.timestamp())
            else:
                return 0

        def _get_tags(obj):
            try:
                return [t["label"] for t in get_tags(obj)]
            except:  # noqa
                return []

        title = _get_attr(obj, "title", "name")
        summary = _get_attr(obj, "summary", "description")
        content = _get_attr(obj, "content")
        tags = _get_tags(obj)

        return {
            "id": str(obj.id),
            "title": title,
            "summary": summary,
            "text": title + " " + content + " " + summary,
            "author": "",
            "timestamp": _get_timestamp(obj),
            "tags": tags,
            "url": url_for(obj),
        }

    @singledispatchmethod
    def adapt(self, obj):
        return self._adapt(obj)

    @adapt.register
    def _(self, user: User):
        data = self._adapt(user)
        data["title"] = user.first_name + " " + user.last_name
        data["summary"] = user.job_title
        data["text"] = " ".join([
            user.first_name,
            user.last_name,
            user.job_title,
            user.profile.presentation,
            # TODO: add more fields
        ])
        return data
