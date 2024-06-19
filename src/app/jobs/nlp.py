# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# from __future__ import annotations
#
# import contextlib
# import re
# from collections import Counter
# from typing import Any, cast
#
# from app.lib import ioc
# from app.services.tagging import add_tag
#
# with contextlib.suppress(ImportError):
#     import spacy
#     import spacy.cli
#     import sqlalchemy as sa
#     from spacy import Language
#
# from bs4 import BeautifulSoup
#
# from app.flask.extensions import db
# from app.flask.lib.jobs import Job
# from app.models.content.textual import Article
#
# MODELS: dict[str, Language] = {
#     # "en": None,
#     # "fr": None,
# }
# LANG_TO_MODEL = {
#     "en": "en_core_web_md",
#     "fr": "fr_core_news_lg",
# }
#
#
# def get_language_model(lang: str) -> Language | None:
#     if MODELS.get(lang):
#         return MODELS[lang]
#
#     if lang not in LANG_TO_MODEL:
#         return None
#
#     model_name = LANG_TO_MODEL[lang]
#
#     try:
#         model = spacy.load(model_name)
#     except OSError:
#         print(f"Downloading model for lang {lang!r}")
#         spacy.cli.download(model_name)
#         model = spacy.load(model_name)
#
#     MODELS[lang] = model
#     return model
#
#
# GOOD_LABELS = {
#     "ORG",
#     "PROD",
#     "PER",
#     "LOC",
#     "MISC",
# }
#
#
# def analyze_article(article: Article) -> None:
#     entities: Any = Counter()
#
#     language_model_or_none = get_language_model("fr")
#     assert language_model_or_none is not None
#     language_model = cast(Language, language_model_or_none)
#
#     text = article.title
#     text += " " + BeautifulSoup(article.content).text
#
#     doc = language_model(text)
#
#     for ent in doc.ents:
#         entity = normalize(ent.text)
#         label = ent.label_
#
#         # if label not in GOOD_LABELS:
#         #     continue
#
#         entities.update([(entity, label)])
#
#     for k, _v in entities.items():
#         # if v < 2:
#         #     continue
#         label = k[0]
#         tag = add_tag(article, k[0])
#         db.session.add(tag)
#
#
# def normalize(s: str) -> str:
#     return re.sub(r"\s+", " ", s).strip()
#
#
# def tag_articles() -> None:
#     stmt = sa.select(Article)
#     articles = list(db.session.execute(stmt).scalars())
#     for article in articles:
#         print(article)
#         analyze_article(article)
#     db.session.commit()
#
#
# @ioc.register
# class NlpJob(Job):
#     name = "nlp"
#     description = "Run NLP tools on the document base"
#
#     def run(self, *args) -> None:
#         tag_articles()
