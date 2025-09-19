# TODO

## Typechecking

### 2025/09/19

mypy: Found 280 errors in 81 files (checked 487 source files)
pyright: 310 errors, 0 warnings, 0 informations
pyrefly: INFO 573 errors (21 ignored)

Typeguard errors:

=================================================== FAILURES ====================================================
_____________________________________________ test_followers_users ______________________________________________
src/app/services/social_graph/test_social_graph.py:44: in test_followers_users
    assert len(social_jim.get_followees()) == 0
               ^^^^^^^^^^^^^^^^^^^^^^^^^^
src/app/services/social_graph/_adapters.py:107: in get_followees
    def get_followees(
.venv/lib/python3.12/site-packages/typeguard/_functions.py:137: in check_argument_types
    check_type_internal(value, annotation, memo)
.venv/lib/python3.12/site-packages/typeguard/_checkers.py:960: in check_type_internal
    checker(value, origin_type, args, memo)
.venv/lib/python3.12/site-packages/typeguard/_checkers.py:511: in check_class
    raise TypeCheckError(
E   typeguard.TypeCheckError: argument "cls" (class app.models.auth.User) is not a subclass of app.models.mixins.IdMixin
__________________________________________________ test_likes ___________________________________________________
src/app/services/social_graph/test_social_graph.py:105: in test_likes
    social_joe.like(social_article)
src/app/services/social_graph/_adapters.py:190: in like
    def like(self, content: BaseContent) -> None:
.venv/lib/python3.12/site-packages/typeguard/_functions.py:137: in check_argument_types
    check_type_internal(value, annotation, memo)
.venv/lib/python3.12/site-packages/typeguard/_checkers.py:965: in check_type_internal
    raise TypeCheckError(f"is not an instance of {qualified_name(origin_type)}")
E   typeguard.TypeCheckError: argument "content" (app.services.social_graph._adapters.SocialContent) is not an instance of app.models.base_content.BaseContent
___________________________________________________ test_tags ___________________________________________________
src/app/services/tagging/tests/test_tagging.py:27: in test_tags
    tag = add_tag(article, "xxx")
          ^^^^^^^^^^^^^^^^^^^^^^^
src/app/services/tagging/_services.py:16: in add_tag
    def add_tag(obj: Taggable, label: str, type: str = "manual") -> TagApplication:
.venv/lib/python3.12/site-packages/typeguard/_functions.py:137: in check_argument_types
    check_type_internal(value, annotation, memo)
.venv/lib/python3.12/site-packages/typeguard/_checkers.py:965: in check_type_internal
    raise TypeCheckError(f"is not an instance of {qualified_name(origin_type)}")
E   typeguard.TypeCheckError: argument "obj" (app.modules.wire.models.ArticlePost) is not an instance of app.services.tagging.interfaces.Taggable
============================================ short test summary info ============================================
FAILED src/app/services/social_graph/test_social_graph.py::test_followers_users - typeguard.TypeCheckError: argument "cls" (class app.models.auth.User) is not a subclass of app.models.mixins...
FAILED src/app/services/social_graph/test_social_graph.py::test_likes - typeguard.TypeCheckError: argument "content" (app.services.social_graph._adapters.SocialContent) is not an i...
FAILED src/app/services/tagging/tests/test_tagging.py::test_tags - typeguard.TypeCheckError: argument "obj" (app.modules.wire.models.ArticlePost) is not an instance of app.ser...
============================= 3 failed, 67 passed, 22 skipped, 3 warnings in 5.44s ==============================
