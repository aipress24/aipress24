# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

# from functools import singledispatch
# from typing import Any, Union
#
# import pendulum
# from sqlalchemy.engine import ScalarResult
#
# from app.flask.routing import url_for
# from app.models.auth import User
# from app.models.content.events import Event, PressEvent, PublicEvent, TrainingEvent
# from app.models.content.textual import Article
#
# JSONType = Union[dict[str, Any], list[Any], int, str, float, bool, type[None]]
#
#
# # NS = "wire"
#
#
# @singledispatch
# def to_json(obj, for_multi=False) -> JSONType:
#     raise RuntimeError
#
#
# @to_json.register
# def to_json_str(obj: str) -> str:
#     return obj
#
#
# @to_json.register
# def to_json_int(obj: int) -> int:
#     return obj
#
#
# @to_json.register
# def to_json_list(objs: list) -> list[dict]:
#     return [to_json(obj, for_multi=True) for obj in objs]  # type: ignore
#
#
# @to_json.register
# def to_json_scalarresult(objs: ScalarResult) -> list[dict]:
#     return to_json(list(objs))  # type: ignore
#
#
# @to_json.register
# def to_json_user(user: User, for_multi=False) -> dict[str, Any]:
#     result = {
#         "id": user.id,
#         "url": url_for(user),
#         #
#         "firstName": user.first_name,
#         "lastName": user.last_name,
#         "name": user.full_name,
#         "organisation": None,  # Was: user.organisation,
#         "profileImageUrl": user.profile_image_url,
#         "role": user.role,
#     }
#     return result
#
#
# @to_json.register
# def to_json_article(article: Article, for_multi=False) -> dict[str, Any]:
#     if article.published_at:
#         published_at = pendulum.from_timestamp(article.published_at.timestamp())
#         age = published_at.diff_for_humans(locale="fr")
#     else:
#         age = "(not set)"
#     return {
#         "id": article.id,
#         "url": url_for(article),
#         #
#         "title": article.title,
#         "abstract": article.subheader,
#         "age": age,
#         "author": to_json(article.owner),
#         "body": article.content,
#         "category": article.category,
#         "imageUrl": article.image_url,
#         #
#         "likes": article.like_count,
#         "replies": article.comment_count,
#         "views": article.view_count,
#     }
#
#
# @to_json.register
# def to_json_event(event: Event, for_multi=False) -> dict:
#     if isinstance(event, PublicEvent):
#         category = "Public"
#     elif isinstance(event, PressEvent):
#         category = "Presse"
#     elif isinstance(event, TrainingEvent):
#         category = "Training"
#     else:
#         raise RuntimeError
#
#     return {
#         "id": event.id,
#         "url": url_for(event),
#         #
#         "title": event.title,
#         # "abstract": event.subheader,
#         "age": event.start_date.strftime("%d/%m/%Y"),
#         "author": to_json(event.owner),
#         # "body": event.body_html,
#         "category": category,
#         # "imageUrl": event.image_url,
#         #
#         "likes": event.like_count,
#         "replies": event.comment_count,
#         "views": event.view_count,
#     }
