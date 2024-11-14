# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import random

from app.modules.swork.models import Comment, Post

from .base import BaseGenerator


class CommentGenerator(BaseGenerator):
    def make_obj(self) -> Comment:
        users = self.repository["users"]

        comment = Comment()
        comment.owner = random.choice(users)
        comment.created_at = self.generate_date()
        comment.content = self.generate_html(min_sentences=1, max_sentences=3)

        article = random.choice(self.repository["articles"])
        comment.object_id = f"article:{article.id}"

        return comment


class PostGenerator(BaseGenerator):
    def make_obj(self) -> Post:
        users = self.repository["users"]

        post = Post()
        post.owner = random.choice(users)
        post.created_at = self.generate_date()
        post.content = self.generate_html(min_sentences=1, max_sentences=3)

        return post
