"""Adapters between SQLAlchemy models and wesh documents.

Three singledispatch surfaces:

* ``doc_type(obj)`` — the type discriminator string stored on every
  index doc (``"article"``, ``"mission_offer"`` etc.). Used as the
  ``type:pk`` prefix in the composite id and as the filter value at
  query time.

* ``to_doc(obj)`` — produce the dict that ``SearchEngine.upsert`` expects.

* ``is_public(obj)`` — decide whether an object should currently be in
  the index. The receiver in ``search/receivers.py`` calls this on
  every domain event and either upserts or deletes accordingly. The
  CLI's ``rebuild`` walks all candidate rows and keeps the ones where
  ``is_public`` is True.

Adding a new indexable type means: register ``doc_type``, ``to_doc``,
``is_public`` for it, and add a domain signal that fires when the
public status flips.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from functools import singledispatch
from typing import Any

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.biz.models import MarketplaceContent
from app.modules.events.models import EventPost
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.services.tagging import get_tags

TagLoader = Callable[[Any], Iterable[dict[str, Any]]]


@singledispatch
def doc_type(obj: Any) -> str:
    """Return the type discriminator for ``obj``."""
    msg = f"No doc_type adapter registered for {type(obj).__name__}"
    raise TypeError(msg)


@singledispatch
def to_doc(obj: Any) -> dict[str, Any]:
    """Return the wesh document for ``obj``. Raises for unknown types."""
    msg = f"No to_doc adapter registered for {type(obj).__name__}"
    raise TypeError(msg)


@singledispatch
def is_public(obj: Any) -> bool:
    """Return True iff ``obj`` should currently appear in the search
    index. False otherwise (drafts, expired, archived, deleted).
    Raises for unknown types.
    """
    msg = f"No is_public adapter registered for {type(obj).__name__}"
    raise TypeError(msg)


def doc_id(obj: Any) -> str:
    """The composite id (``"<type>:<pk>"``) for ``obj``. Cheap to compute
    — skips the URL/tags lookups that ``to_doc`` does — so it's safe to
    call on the delete path without paying the upsert price.
    """
    return f"{doc_type(obj)}:{obj.id}"


# ── Common helpers ──────────────────────────────────────────────────


def _to_datetime(value: Any) -> datetime | None:
    """Unwrap ``arrow.Arrow`` to a plain ``datetime``. wesh's DATETIME
    field uses ``isinstance(x, datetime.datetime)`` which Arrow fails."""
    if value is None:
        return None
    inner = getattr(value, "datetime", None)
    if isinstance(inner, datetime):
        return inner
    return value


def _format_tags(applications: Iterable[dict[str, Any]]) -> str:
    """Pure: render the comma-separated label list for the
    ``KEYWORD(commas=True)`` field. Empty / missing labels are skipped."""
    return ",".join(t["label"] for t in applications if t.get("label"))


def _tags(obj: Any, *, loader: TagLoader = get_tags) -> str:
    """Comma-separated tag labels for the ``KEYWORD(commas=True)`` field.

    ``loader`` is dependency-injected for testability — defaults to the
    real :func:`app.services.tagging.get_tags`, which hits the DB. The
    try/except is the production safety net for the "no session" path
    (e.g. an event fired during app bootstrap)."""
    try:
        applications = loader(obj)
    except Exception:  # pragma: no cover  defensive
        return ""
    return _format_tags(applications)


def _is_publicly_visible(obj: Any, expiry_attr: str) -> bool:
    """Shared public-visibility check for content with a publication
    lifecycle (status + published_at + optional expiry timestamp).
    """
    if getattr(obj, "status", None) != PublicationStatus.PUBLIC:
        return False
    if _to_datetime(getattr(obj, "published_at", None)) is None:
        return False
    expiry = _to_datetime(getattr(obj, expiry_attr, None))
    return expiry is None or expiry > datetime.now(tz=UTC)


def _build_doc(obj: Any) -> dict[str, Any]:
    """Shared shape for every indexable document. ``description`` is
    used where ``summary`` isn't a model attribute (marketplace).
    """
    title = obj.title or ""
    content = getattr(obj, "content", "") or ""
    summary = getattr(obj, "summary", None) or getattr(obj, "description", "") or ""
    type_name = doc_type(obj)
    return {
        "type": type_name,
        "id": f"{type_name}:{obj.id}",
        "title": title,
        "text": " ".join(filter(None, [title, content, summary])),
        "summary": summary,
        "url": url_for(obj),
        "timestamp": _to_datetime(getattr(obj, "published_at", None)),
        "tags": _tags(obj),
    }


# ── ArticlePost ─────────────────────────────────────────────────────


@doc_type.register
def _(_: ArticlePost) -> str:
    return "article"


@to_doc.register
def _(obj: ArticlePost) -> dict[str, Any]:
    return _build_doc(obj)


@is_public.register
def _(obj: ArticlePost) -> bool:
    return _is_publicly_visible(obj, expiry_attr="expires_at")


# ── PressReleasePost ────────────────────────────────────────────────


@doc_type.register
def _(_: PressReleasePost) -> str:
    return "press_release"


@to_doc.register
def _(obj: PressReleasePost) -> dict[str, Any]:
    return _build_doc(obj)


@is_public.register
def _(obj: PressReleasePost) -> bool:
    return _is_publicly_visible(obj, expiry_attr="expires_at")


# ── EventPost ───────────────────────────────────────────────────────


@doc_type.register
def _(_: EventPost) -> str:
    return "event"


@to_doc.register
def _(obj: EventPost) -> dict[str, Any]:
    return _build_doc(obj)


@is_public.register
def _(obj: EventPost) -> bool:
    return _is_publicly_visible(obj, expiry_attr="expired_at")


# ── Marketplace (Mission/Project/Job/EditorialProduct) ──────────────
#
# Registered against the polymorphic base class; singledispatch walks
# the MRO so all four subclasses dispatch here. The per-row ``type``
# discriminator (``"mission_offer"`` etc.) comes from the SQLAlchemy
# polymorphic identity, already stored on the instance as ``obj.type``.
#
# Marketplace lifecycle does not currently set ``published_at`` — the
# moderation flow only flips ``status``. So ``is_public`` here is a
# plain status check, distinct from the post/event helper which also
# requires a publication timestamp.


@doc_type.register
def _(obj: MarketplaceContent) -> str:
    return obj.type


@to_doc.register
def _(obj: MarketplaceContent) -> dict[str, Any]:
    return _build_doc(obj)


@is_public.register
def _(obj: MarketplaceContent) -> bool:
    return obj.status == PublicationStatus.PUBLIC


# ── Group (swork) ────────────────────────────────────────────────────
# Retiré de la recherche le 2026-05-21 — l'adapter et le receiver ne
# sont plus enregistrés.


# ── User (members) ───────────────────────────────────────────────────
#
# A user is searchable once they've been validated by an admin AND
# are still active. ``deleted_at`` is the soft-delete marker — set on
# rejection, gone-from-search even if active=True (paranoid).


@doc_type.register
def _(_: User) -> str:
    return "user"


@to_doc.register
def _(obj: User) -> dict[str, Any]:
    # See note on the Group adapter — ``str()`` coercion to satisfy
    # pyrefly's view of SQLAlchemy descriptor typing.
    first_name = str(obj.first_name or "")
    last_name = str(obj.last_name or "")
    title = obj.full_name.strip() or str(obj.email or "")
    profile = getattr(obj, "profile", None)
    job_title = str(
        (getattr(profile, "profile_label", "") if profile is not None else "") or ""
    )
    presentation = str(
        (getattr(profile, "presentation", "") if profile is not None else "") or ""
    )
    return {
        "type": "user",
        "id": f"user:{obj.id}",
        "title": title,
        "text": " ".join(
            filter(None, [first_name, last_name, job_title, presentation])
        ),
        "summary": job_title,
        "url": url_for(obj),
        "timestamp": _to_datetime(
            getattr(obj, "validated_at", None) or getattr(obj, "created_at", None)
        ),
        "tags": "",
    }


@is_public.register
def _(obj: User) -> bool:
    if not obj.active:
        return False
    if obj.validated_at is None:
        return False
    return getattr(obj, "deleted_at", None) is None


# ── Organisation ─────────────────────────────────────────────────────


@doc_type.register
def _(_: Organisation) -> str:
    return "organisation"


@to_doc.register
def _(obj: Organisation) -> dict[str, Any]:
    # See note on the Group adapter — ``str()`` coercion to satisfy
    # pyrefly's view of SQLAlchemy descriptor typing.
    name = str(obj.name or "")
    bw_name = str(obj.bw_name or "")
    return {
        "type": "organisation",
        "id": f"organisation:{obj.id}",
        "title": name,
        "text": " ".join(filter(None, [name, bw_name])),
        "summary": bw_name,
        "url": url_for(obj),
        "timestamp": _to_datetime(getattr(obj, "created_at", None)),
        "tags": "",
    }


@is_public.register
def _(obj: Organisation) -> bool:
    if not obj.active:
        return False
    return getattr(obj, "deleted_at", None) is None
