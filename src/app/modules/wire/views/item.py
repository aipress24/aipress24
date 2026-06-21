# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Wire item page - article and press release detail views."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING, ClassVar, cast

import arrow
import sqlalchemy as sa
import stripe
import stripe.error
from attr import field, frozen
from babel.numbers import format_currency
from cachetools import TTLCache
from flask import current_app, flash, g, redirect, render_template, request
from flask.views import MethodView
from sqlalchemy.orm import selectinload
from werkzeug import Response

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.lib.view_model import Wrapper
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.logging import warn
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.kyc.field_label import (
    country_code_to_label,
    country_zip_code_to_city,
)
from app.modules.swork.models import Comment
from app.modules.wire import blueprint
from app.modules.wire.models import (
    ArticlePost,
    Post,
    PressReleasePost,
    PurchaseProduct,
)
from app.modules.wire.views.purchase import _price_id_for
from app.services.social_graph import SocialUser, adapt
from app.services.stripe.utils import load_stripe_api_key
from app.services.tagging import get_tags
from app.services.tracking import record_view

# Cache formatted Stripe price strings for the paywall button.
_CONSULTATION_PRICE_CACHE: TTLCache[str, str] = TTLCache(maxsize=256, ttl=3600)


def _fetch_consultation_price(price_id: str) -> str:
    """Fetch a Stripe Price by id, format it for display, and cache it."""
    cached = _CONSULTATION_PRICE_CACHE.get(price_id)
    if cached is not None:
        return cached

    if not load_stripe_api_key():
        return ""

    try:
        live_price = stripe.Price.retrieve(price_id)
        if live_price.unit_amount is None:
            return ""
        amount = Decimal(live_price.unit_amount) / Decimal(100)
        display = format_currency(
            amount,
            live_price.currency.upper(),
            locale="fr_FR",
        ).replace(" ", " ")
    except stripe.error.StripeError as exc:
        warn(f"item: failed to retrieve price {price_id}: {exc}")
        return ""

    _CONSULTATION_PRICE_CACHE[price_id] = display
    return display


class ItemDetailView(MethodView):
    """Article/Press Release detail page with actions."""

    decorators: ClassVar[list] = [nav(parent="wire", label="Article")]

    def get(self, id: str):
        post = get_obj(id, Post)

        match post:
            case ArticlePost():
                view_model = ArticleVM(post)
                template = "pages/article.j2"
            case PressReleasePost():
                view_model = PressReleaseVM(post)
                template = "pages/press-release.j2"
            case _:
                msg = f"Unknown item type: {post}"
                raise TypeError(msg)

        # Set dynamic breadcrumb label
        g.nav.label = post.title

        # Record view
        record_view(g.user, post)
        db.session.commit()

        # Build metadata
        metadata_list = self._get_metadata_list(post)

        from app.modules.bw.bw_activation.rights_policy import (
            is_eligible_for_cession,
        )
        from app.modules.wire.services.article_access import (
            truncate_body,
            user_can_read_full,
        )

        can_cede = is_eligible_for_cession(g.user, post)
        can_read_full = user_can_read_full(g.user, post)
        # Ticket #0212: only truncate when the paywall is actually live.
        # Before go-live (flag off) a non-buyer can't purchase anyway, so a
        # truncated body with no buy CTA is a dead-end — show the full text.
        paywall_active = bool(current_app.config.get("STRIPE_LIVE_ENABLED"))
        if can_read_full or not paywall_active:
            body_preview = post.content
        else:
            body_preview = truncate_body(post.content)

        consultation_price_str = ""
        if not can_read_full and current_app.config.get("STRIPE_LIVE_ENABLED"):
            price_id = _price_id_for(
                PurchaseProduct.CONSULTATION, genre=getattr(post, "genre", "") or ""
            )
            if price_id:
                consultation_price_str = _fetch_consultation_price(price_id)

        return render_template(
            template,
            title=post.title,
            post=view_model,
            metadata_list=metadata_list,
            can_cede=can_cede,
            can_read_full=can_read_full,
            body_preview=body_preview,
            consultation_price_str=consultation_price_str,
        )

    def post(self, id: str) -> str | Response:
        post = get_obj(id, Post)
        action = request.form["action"]

        match action:
            case "toggle-like":
                return self._toggle_like(post)
            case "post-comment":
                return self._post_comment(post)
            case _:
                return ""

    def _toggle_like(self, article) -> str:
        """Toggle like status for the current user on the given article."""
        user: SocialUser = adapt(g.user)
        if user.is_liking(article):
            user.unlike(article)
        else:
            user.like(article)
        db.session.flush()
        article.like_count = adapt(article).num_likes()
        db.session.commit()
        return str(article.like_count)

    def _post_comment(self, post: Post) -> Response:
        """Post a comment on the given post (article or press release)."""
        user = g.user
        comment_text = request.form["comment"].strip()
        if comment_text:
            comment = Comment()
            comment.content = comment_text
            comment.owner = user
            comment.object_id = _get_comment_object_id(post)
            db.session.add(comment)
            post.comment_count += 1
            db.session.commit()
            flash("Votre commentaire a été posté.")

        return redirect(url_for(post) + "#comments-title")

    def _get_metadata_list(self, post: Post) -> list[dict]:
        """Build metadata list for display."""
        return build_metadata_list(post)


# =============================================================================
# Pure helpers (mock-free unit-testable)
# =============================================================================


_POST_TYPE_LABELS: dict[str, str] = {
    "article": "Article",
    "press_release": "Communiqué",
}


def post_type_label(type_str: str | None) -> str:
    """Map a post.type string to its French display label.

    Pure lookup over `_POST_TYPE_LABELS` with a fallback for unknown
    or missing types. Extracted from the nested `post_type()` closure
    inside `_get_metadata_list` so it can be tested without a Post.
    """
    if not type_str:
        return "Non classé"
    return _POST_TYPE_LABELS.get(type_str, "Non classé")


def build_metadata_list(
    post,
    *,
    country_label: Callable[[str], str] = country_code_to_label,
    city_label: Callable[[str], str] = country_zip_code_to_city,
) -> list[dict]:
    """Build the [{label, value}] metadata list shown next to a post.

    Pure transformation : reads attributes off `post` (duck-typed) and
    routes the two ontology lookups through injected callables so
    tests can pass plain `def fake(code): return ...` stubs without
    loading the KYC ontologies. Production callers keep the defaults.
    """
    data = [
        {"label": "Type", "value": post_type_label(getattr(post, "type", None))},
        {"label": "Genre", "value": post.genre or "N/A"},
        {"label": "Rubrique", "value": post.section or "N/A"},
        {"label": "Sujet", "value": post.topic or "N/A"},
        {"label": "Secteur d'activité", "value": post.sector or "N/A"},
    ]

    if post.address:
        data.append({"label": "Adresse", "value": post.address})
    if post.pays_zip_ville:
        data.append({"label": "Pays", "value": country_label(post.pays_zip_ville)})
    if post.pays_zip_ville_detail:
        data.append({"label": "Ville", "value": city_label(post.pays_zip_ville_detail)})

    return data


def _get_comment_object_id(post: Post) -> str:
    """Get the comment object_id for a post based on its type."""
    match post:
        case ArticlePost():
            return f"article:{post.id}"
        case PressReleasePost():
            return f"press-release:{post.id}"
        case _:
            return f"post:{post.id}"


# Register the view
blueprint.add_url_rule(
    "/<id>",
    view_func=ItemDetailView.as_view("item"),
)


# =============================================================================
# ViewModels
# =============================================================================


class PostMixin:
    """Mixin for common post attributes."""

    if TYPE_CHECKING:
        _model: Post
        publisher: Organisation

    def extra_attrs(self):
        post = self._model
        return {
            "age": "?",
            "author": UserVM(post.owner),
            "summary": post.summary,
            "likes": post.like_count,
            "replies": post.comment_count,
            "views": post.view_count,
            "num_likes": post.like_count,
            "num_replies": post.comment_count,
            "num_views": post.view_count,
            "num_comments": post.comment_count,
            "comments": [],
            "tags": get_tags(post),
            "_url": url_for(post),
            "type": post.type,
        }

    def get_publisher_type(self):
        # FIXME: publisher (Organisation) has no type,

        # publisher = self.publisher
        # if publisher:
        #     match publisher.type:
        #         case OrganisationTypeEnum.MEDIA:
        #             publisher_type = "Publié par (Média)"
        #         case OrganisationTypeEnum.AGENCY:
        #             publisher_type = "Publié par (Agence de presse)"
        #         case OrganisationTypeEnum.COM:
        #             publisher_type = "Publié par (PR Agency)"
        #         case _:
        #             publisher_type = "Publié par"
        # else:
        #     publisher_type = "Publié par"
        publisher_type = "Publié par"
        return publisher_type


class PostVMMixin(PostMixin):
    """Shared ViewModel mixin for Article and Press Release posts.

    Subclasses must define:
    - _model: The post model instance
    - _comment_prefix: Prefix for comment object_id (e.g., "article", "press-release")
    """

    _comment_prefix: str

    def extra_attrs(self) -> dict:
        post = self._model

        if post.published_at:
            age = cast(arrow.Arrow, post.published_at).humanize(locale="fr")
        else:
            age = "(not set)"

        # `super().extra_attrs()` already builds author / tags / _url —
        # don't recompute them here (each rebuilt UserVM re-queried the
        # org, each get_tags() re-queried tag_application). Only override
        # what actually differs for a published post.
        extra_attrs = super().extra_attrs()
        extra_attrs.update(
            {
                "age": age,
                "publisher_type": self.get_publisher_type(),
                "comments": self.get_comments(),
            }
        )
        return extra_attrs

    def get_comments(self) -> list[Comment]:
        post = self._model
        object_id = f"{self._comment_prefix}:{post.id}"
        stmt = (
            sa.select(Comment)
            .where(Comment.object_id == object_id)
            .order_by(Comment.created_at.desc())
            .options(selectinload(Comment.owner))
        )
        return list(db.session.scalars(stmt))


@frozen
class ArticleVM(PostVMMixin, Wrapper):
    """ViewModel for Article posts."""

    _model: ArticlePost
    _comment_prefix: str = "article"
    _url: str = field(init=False)

    author: User = field(init=False)

    likes: int = field(init=False)
    replies: int = field(init=False)
    views: int = field(init=False)

    num_likes: int = field(init=False)
    num_replies: int = field(init=False)
    num_views: int = field(init=False)
    num_comments: int = field(init=False)

    summary: str = field(init=False)
    age: int = field(init=False)
    comments: list = field(init=False)
    tags: list = field(init=False)

    publisher: Organisation = field(init=False)
    publisher_type: str = field(init=False)


@frozen
class PressReleaseVM(PostVMMixin, Wrapper):
    """ViewModel for Press Release posts."""

    _model: PressReleasePost
    _comment_prefix: str = "press-release"
    _url: str = field(init=False)

    author: User = field(init=False)

    likes: int = field(init=False)
    replies: int = field(init=False)
    views: int = field(init=False)

    num_likes: int = field(init=False)
    num_replies: int = field(init=False)
    num_views: int = field(init=False)
    num_comments: int = field(init=False)

    summary: str = field(init=False)
    age: int = field(init=False)
    comments: list = field(init=False)
    tags: list = field(init=False)

    publisher: Organisation = field(init=False)
    publisher_type: str = field(init=False)


@frozen
class UserVM(Wrapper):
    """ViewModel for User."""

    organisation: Organisation | None = field(init=False)
    _url: str = field(init=False)

    def extra_attrs(self):
        user = self._model
        return {
            "_url": url_for(user),
            "organisation": self.get_organisation(),
        }

    def get_organisation(self) -> Organisation | None:
        # `User.organisation_id` is nullable (auth.py): an author with
        # no organisation must not 500 the article / press-release
        # page. The eager `Wrapper.extra_attrs()` builds this VM for
        # every render, so a bare `assert result` here took the whole
        # page down (audit C1, same class as the events orgless-
        # participant crash). Mirror the safe twin in
        # `common/components/post_card.py:UserVM` — return None and let
        # the template guard with `{% if author.organisation %}`.
        user = cast("User", self._model)
        if user.organisation_id is None:
            return None
        stmt = (
            sa.select(Organisation)
            .where(Organisation.id == user.organisation_id)
            .order_by(Organisation.name)
        )
        return db.session.scalar(stmt)
