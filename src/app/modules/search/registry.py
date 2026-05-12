"""Single source of truth for indexable types.

Before this module existed, the list of indexable types was duplicated
across four files:

* ``constants.COLLECTIONS`` — UI sidebar entries
* ``jobs._POST_LOOKUP`` — signal-source → model lookup map
* ``cli._INDEXABLE_TYPES`` — bulk-rebuild walk targets
* ``adapters`` — per-type ``doc_type`` / ``to_doc`` / ``is_public`` dispatch

Each was correct in isolation but adding a new type meant editing all
four. The first three are derivable from a single registry; the
``adapters`` singledispatch surface stays per-type because the bodies
genuinely differ (different field surfaces, different visibility rules).

Adding a new indexable type now means:

1. Append an :class:`IndexableType` entry to :data:`REGISTRY` below.
2. Register ``doc_type`` / ``to_doc`` / ``is_public`` in ``adapters.py``.
3. Add a domain signal in ``signals.py`` and a receiver in
   ``receivers.py`` that calls ``reindex_from_source.send(source_type, id)``.
4. Emit the signal at the relevant page handler call sites.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.biz.models import MarketplaceContent
from app.modules.events.models import EventPost
from app.modules.swork.models import Group
from app.modules.wire.models import ArticlePost, PressReleasePost


@dataclass(frozen=True)
class IndexableType:
    """Static description of one indexable kind."""

    source_type: str
    """Discriminator passed to ``reindex_from_source.send(source_type, id)``.
    Receivers know this; the job dispatcher resolves it via :data:`REGISTRY`.
    """

    model: type
    """SQLAlchemy class to walk in ``flask search rebuild`` and to use
    for source-to-instance lookups. May be a polymorphic base class —
    in that case the walk and the lookup return concrete subclasses.
    """

    fk_column: str | None
    """Column on ``model`` that holds the signal source's id (e.g.
    ``newsroom_id`` for wire posts that mirror a wip Article). ``None``
    means the signal source IS the indexable instance — look up by
    primary key.
    """

    ui_name: str
    """URL filter token (``/search/?filter=articles``) and sidebar key."""

    label: str
    """Sidebar label."""

    icon: str
    """Sidebar icon name."""

    doc_types: tuple[str, ...]
    """The ``type`` discriminator(s) stored on indexed documents for
    this UI bucket. Single value for most types; multiple for
    polymorphic buckets (marketplace = 4 subtypes share one bucket).
    """


REGISTRY: tuple[IndexableType, ...] = (
    IndexableType(
        source_type="article",
        model=ArticlePost,
        fk_column="newsroom_id",
        ui_name="articles",
        label="Articles",
        icon="newspaper",
        doc_types=("article",),
    ),
    IndexableType(
        source_type="press_release",
        model=PressReleasePost,
        fk_column="newsroom_id",
        ui_name="press-releases",
        label="Communiqués",
        icon="speaker-wave",
        doc_types=("press_release",),
    ),
    IndexableType(
        source_type="event",
        model=EventPost,
        fk_column="eventroom_id",
        ui_name="events",
        label="Événements",
        icon="calendar",
        doc_types=("event",),
    ),
    IndexableType(
        source_type="marketplace",
        model=MarketplaceContent,
        fk_column=None,
        ui_name="marketplace",
        label="Marketplace",
        icon="shopping-bag",
        doc_types=(
            "mission_offer",
            "project_offer",
            "job_offer",
            "editorial_product",
        ),
    ),
    IndexableType(
        source_type="group",
        model=Group,
        fk_column=None,
        ui_name="groups",
        label="Groupes",
        icon="user-group",
        doc_types=("group",),
    ),
    IndexableType(
        source_type="user",
        model=User,
        fk_column=None,
        ui_name="members",
        label="Membres",
        icon="user",
        doc_types=("user",),
    ),
    IndexableType(
        source_type="organisation",
        model=Organisation,
        fk_column=None,
        ui_name="orgs",
        label="Organisations",
        icon="building-office",
        doc_types=("organisation",),
    ),
)


def lookup_by_source_type(source_type: str) -> IndexableType:
    """Find the registry entry matching a signal ``source_type``.

    Raises ``KeyError`` if unknown — receivers and the job dispatcher
    only pass values they put into the registry themselves, so a miss
    is a programming error worth surfacing.
    """
    for entry in REGISTRY:
        if entry.source_type == source_type:
            return entry
    msg = f"Unknown source_type: {source_type!r}"
    raise KeyError(msg)
