# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Wire item page - article and press release detail views."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, ClassVar, cast

import arrow
import sqlalchemy as sa
from attr import field, frozen
from flask import (
    current_app,
    flash,
    g,
    make_response,
    redirect,
    render_template,
    request,
)
from flask.views import MethodView
from sqlalchemy.orm import selectinload
from werkzeug import Response
from werkzeug.exceptions import BadRequest, Forbidden

from app.constants import CONTENT_ALERT_REASONS
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.lib.toaster import toast
from app.flask.lib.view_model import Wrapper
from app.flask.routing import url_for
from app.flask.sqla import get_public_obj
from app.logging import warn
from app.models.auth import User
from app.models.content_alert import ContentAlert
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
from app.modules.wire.services.recipients import parse_recipient_emails
from app.modules.wire.views.purchase import _price_id_for
from app.services.emails.mailers import ContentAlertMail, ShareContentMail
from app.services.social_graph import SocialUser, adapt
from app.services.stripe.prices import stripe_price_display
from app.services.tagging import get_tags
from app.services.tracking import record_view


def _paywall_context(post: Post, user: User) -> dict:
    """Everything the paywall has to say about this (article, reader).

    Extracted from `ItemDetailView.get`, which chained dispatch, the
    breadcrumb, view recording, metadata, six local imports, eight
    access computations, a price lookup and an invitation query before
    rendering twelve variables: you could no longer say what it did
    without an "and" (audit 2026-09-02).

    `user` is a signed-in member: the blueprint's `before_request`
    guarantees that for every `/wire/*` view.
    """
    from app.modules.bw.bw_activation.rights_policy import is_eligible_for_cession
    from app.modules.wire.services.article_access import (
        get_user_justificatif_purchase_info,
        get_user_purchase_info,
        has_paid_consultation,
        has_received_consultation_gift,
        truncate_body,
        user_can_read_full,
    )

    # The two access lookups, done **once** and reused.
    # `user_can_read_full` already made them internally, and the view
    # repeated them right after with the same arguments: two extra
    # queries on every article page, for any reader who is neither the
    # author nor an admin.
    has_paid = has_paid_consultation(user.id, post.id)
    has_gift = has_received_consultation_gift(user.id, post.id)
    can_read_full = user_can_read_full(
        user,
        post,
        paid_lookup=lambda _uid, _pid: has_paid,
        gift_lookup=lambda _uid, _pid: has_gift,
    )

    # Ticket #0212: only truncate when the paywall is actually live.
    # Before go-live (flag off) a non-buyer can't purchase anyway, so a
    # truncated body with no buy CTA is a dead-end — show the full text.
    paywall_active = bool(current_app.config.get("STRIPE_LIVE_ENABLED"))
    body_preview = (
        post.content
        if can_read_full or not paywall_active
        else truncate_body(post.content)
    )

    consultation_price_str = ""
    if paywall_active and not can_read_full:
        price_id = _price_id_for(PurchaseProduct.CONSULTATION, genre=post.genre)
        consultation_price_str = stripe_price_display(price_id) if price_id else ""

    return {
        "can_cede": is_eligible_for_cession(user, post),
        "can_read_full": can_read_full,
        "user_has_paid_consultation": has_paid,
        "user_has_offered_consultation": has_gift,
        "purchase_info": get_user_purchase_info(user, post),
        "justificatif_purchase_info": get_user_justificatif_purchase_info(user, post),
        "body_preview": body_preview,
        "consultation_price_str": consultation_price_str,
        "has_justificatif_invitation": _has_justificatif_invitation(post, user),
    }


def _has_justificatif_invitation(post: Post, user: User) -> bool:
    """Has the journalist invited this reader for this article?

    That is the only condition for showing the "Justificatif" button.
    """
    from app.modules.wip.models.newsroom.justificatif_invitation import (
        JustificatifInvitation,
    )

    if not isinstance(post, ArticlePost) or not post.newsroom_id:
        return False
    return bool(
        db.session.scalar(
            sa.select(JustificatifInvitation.id)
            .where(JustificatifInvitation.article_id == post.newsroom_id)
            .where(JustificatifInvitation.recipient_id == user.id)
            .limit(1)
        )
    )


class ItemDetailView(MethodView):
    """Article/Press Release detail page with actions."""

    decorators: ClassVar[list] = [nav(parent="wire", label="Article")]

    def get(self, id: str):
        post = get_public_obj(id, Post)

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

        return render_template(
            template,
            title=post.title,
            post=view_model,
            metadata_list=metadata_list,
            **_paywall_context(post, g.user),
        )

    def post(self, id: str) -> str | Response:
        post = get_public_obj(id, Post)
        action = request.form["action"]

        match action:
            case "toggle-like":
                return self._toggle_like(post)
            case "post-comment":
                return self._post_comment(post)
            # case "content-alert":
            #     return self._post_content_alert(post)
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

    # def _post_content_alert(self, post: Post) -> Response:
    #     """Send a content alert for the post."""
    #     response = make_response("", 200)
    #     toast(response, "Signalement envoyé.")
    #     return response

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
            "shares": getattr(post, "share_count", 0),
            "num_likes": post.like_count,
            "num_replies": post.comment_count,
            "num_views": post.view_count,
            "num_shares": getattr(post, "share_count", 0),
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


def _get_form_emails() -> list[str]:
    raw_emails_blob = "\n".join(
        request.form.getlist("recipient_emails")
    ) or request.form.get("recipient_emails", "")
    return parse_recipient_emails(raw_emails_blob)


@blueprint.route("/<post_id>/share_modal", methods=["GET"])
def share_modal(post_id: str) -> str:
    """Modal for sharing content."""
    user = cast(User, g.user)
    if not user or user.is_anonymous:
        msg = "Access denied"
        raise Forbidden(msg)
    post = get_public_obj(post_id, Post)
    post_url = url_for(post, _external=True)
    return render_template(
        "pages/wire/share_modal.j2",
        post=post,
        post_url=post_url,
    )


def _send_shared_content_mail(
    post: Post,
    user: User,
    emails: list[str],
) -> None:
    # For registered users retrieve their full_name
    stmt = sa.select(User).where(sa.func.lower(User.email).in_(emails))
    known_users = db.session.scalars(stmt).all()
    users_by_email = {u.email.lower(): u for u in known_users if u.email}

    for email in emails:
        known_user = users_by_email.get(email)
        recipient_full_name = ""
        if known_user:
            recipient_full_name = known_user.full_name or ""
        try:
            share_mail = ShareContentMail(
                sender="contact@aipress24.com",
                recipient=email,
                sender_mail=user.email,
                recipient_full_name=recipient_full_name,
                giver_full_name=user.full_name or user.email,
                article_title=post.title,
                article_url=url_for(post, _external=True),
            )
            share_mail.send()
        except Exception as e:
            warn(f"Failed to send ShareContentMail to {email} for post {post.id}: {e}")


@blueprint.route("/<post_id>/share", methods=["POST"])
def share_submit(post_id: str) -> Response:
    """Sending emails to share recipients and increment post.share_count."""
    user = cast(User, g.user)
    if not user or user.is_anonymous:
        msg = "Access denied"
        raise Forbidden(msg)

    emails = _get_form_emails()
    if not emails:
        msg = "Veuillez saisir au moins une adresse mail valide."
        raise BadRequest(msg)

    post = get_public_obj(post_id, Post)

    _send_shared_content_mail(post, user, emails)

    post.share_count += len(emails)
    db.session.commit()

    inner_html = (
        f'<span id="shares-{post.id}" class="font-medium text-gray-900" '
        f'hx-swap-oob="innerHTML">{post.share_count}</span>'
    )
    response = make_response(inner_html, 200)
    toast(response, f"Publication partagée avec {len(emails)} destinataire(s).")
    return response


@blueprint.route("/<post_id>/alert_modal", methods=["GET"])
def alert_modal(post_id: str) -> str:
    """HTMX modal for reporting content."""
    user = cast(User, g.user)
    if not user or user.is_anonymous:
        msg = "Access denied"
        raise Forbidden(msg)
    post = get_public_obj(post_id, Post)
    return render_template(
        "pages/wire/alert_modal.j2",
        post=post,
        alert_reasons=CONTENT_ALERT_REASONS,
    )


@blueprint.route("/<post_id>/alert", methods=["POST"])
def alert_submit(post_id: str) -> Response:
    """Handle content alert submission."""
    user = cast(User, g.user)
    if not user or user.is_anonymous:
        msg = "Access denied"
        raise Forbidden(msg)
    post = get_public_obj(post_id, Post)
    message = request.form.get("message", "").strip()
    raw_reasons = request.form.getlist("reasons")
    if not raw_reasons and request.form.get("reasons"):
        raw_reasons = [request.form.get("reasons", "").strip()]
    raw_reasons = [r for r in raw_reasons if r]

    reasons: list[str] = []
    for r in raw_reasons:
        label = CONTENT_ALERT_REASONS.get(r, r)
        if label and label not in reasons:
            reasons.append(label)

    if not reasons:
        msg = "Veuillez sélectionner au moins un motif de signalement."
        raise BadRequest(msg)

    if len(reasons) == 1:
        autre_label = CONTENT_ALERT_REASONS.get("autre")
        if reasons == [autre_label] and not message:
            msg = "Veuillez préciser le champ détails."
            raise BadRequest(msg)

    reason_label = ", ".join(reasons)

    warn(
        f"Content alert for post {post.id} {post.title!r} "
        f"by uid {user.id} {user.email!r}: reasons={reasons!r}"
    )

    post_type = "Communiqué" if isinstance(post, PressReleasePost) else "Article"
    post_author_name = post.owner.full_name if post.owner else ""
    post_url = url_for(post, _external=True)
    try:
        content_alert = ContentAlert(
            post_id=post.id,
            post_title=post.title,
            post_type=post_type,
            post_url=post_url,
            post_author_name=post_author_name,
            reasons=reasons,
            message=message,
            reporter_id=user.id,
            reporter_email=user.email,
            reporter_name=user.full_name,
        )
        db.session.add(content_alert)
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        warn(f"Failed to record content alert in db for post {post_id}: {exc}")

    try:
        alert_mail = ContentAlertMail(
            post_id=post.id,
            post_title=post.title,
            post_url=post_url,
            post_type=post_type,
            post_author_name=post_author_name,
            reason_label=reason_label,
            message=message,
            reporter_email=user.email,
            reporter_name=user.full_name,
        )
        alert_mail.send()
    except Exception as exc:
        warn(f"Failed to send content alert email for post {post.id}: {exc}")

    response = make_response("", 200)
    toast(response, "Signalement envoyé. Merci de votre vigilance.")
    return response
