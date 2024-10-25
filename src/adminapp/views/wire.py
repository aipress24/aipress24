from sqladmin import Admin, ModelView

from app.modules.wire.models import ArticlePost


class PostAdmin(ModelView, model=ArticlePost):
    icon = "fa-solid fa-newspaper"
    category = "Wire"

    column_list = [ArticlePost.id, ArticlePost.created_at, ArticlePost.title]
    column_searchable_list = [ArticlePost.title, ArticlePost.content]
    column_sortable_list = [ArticlePost.created_at]


def register(admin: Admin):
    admin.add_view(PostAdmin)
