# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import Page, page
from app.flask.sqla import get_obj
from app.modules.biz.models import MarketplaceContent

from .home import BizHomePage

# @define
# class ArticleVM(ViewModel):
#     def extra_attrs(self):
#         article = cast(Article, self._model)
#
#         if article.published_at:
#             age = article.published_at.humanize(locale="fr")
#         else:
#             age = "(not set)"
#
#         return {
#             "age": age,
#             #
#             "author": article.owner,
#             #
#             "likes": article.like_count,
#             "comments": article.comment_count,
#             "views": article.view_count,
#             "tags": get_tags(article),
#         }


# Disabled: migrated to views/item.py
# @page
class BizItemPage(Page):
    path = "/<int:id>"
    name = "biz-item"
    template = "pages/biz-item.j2"

    parent = BizHomePage

    def __init__(self, id) -> None:
        self.args = {"id": id}
        self.item = get_obj(id, MarketplaceContent)
        # self.view_model = ArticleVM(self.article)

    @property
    def label(self):
        return self.item.title

    def context(self):
        return {
            "item": self.item,
        }


#     def context(self):
#         return {
#             "article": self.view_model,
#             "comments": self.get_comments(),
#         }
#
#     def get_comments(self) -> list[Comment]:
#         article = self.article
#         stmt = (
#             sa.select(Comment)
#             .where(Comment.object_id == f"article:{article.id}")
#             .order_by(Comment.created_at.desc())
#         )
#         result = db.session.execute(stmt)
#         return list(result.scalars())
#
#     def get(self):
#         record_view(g.user, self.article)
#         db.session.commit()
#         return super().get()
#
#     #
#     # Actions
#     #
#     def post(self) -> str | Response:
#         action = request.form["action"]
#         match action:
#             case "toggle-like":
#                 return self.toggle_like()
#             case "post-comment":
#                 return self.post_comment()
#             case _:
#                 return ""
#
#         # Temp, because mypy is not yet cognizant of pattern-matching
#         return ""
#
#     def toggle_like(self):
#         user = g.user
#         article = self.article
#         if sg.is_liking(user, article):
#             sg.unlike(user, article)
#         else:
#             sg.like(user, article)
#         db.session.flush()
#         article.like_count = sg.likes_count(article)
#         db.session.commit()
#         return str(self.article.like_count)
#
#     def post_comment(self):
#         user = g.user
#         article = self.article
#         comment_text = request.form["comment"].strip()
#         if comment_text:
#             comment = Comment()
#             comment.content = comment_text
#             comment.owner = user
#             comment.object_id = f"article:{article.id}"
#             db.session.add(comment)
#             db.session.commit()
#             flash("Votre commentaire a été posté.")
#
#         return redirect(url_for(article) + "#comments-title")
