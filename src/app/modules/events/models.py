# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from enum import StrEnum, auto
from typing import ClassVar

import arrow
import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    orm,
)
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from sqlalchemy_utils import ArrowType

from app.enums import EventMode, EventPricing
from app.models.auth import User
from app.models.base import Base
from app.models.content.base import BaseContent
from app.models.content.mixins import Publishable, Searchable
from app.models.mixins import Addressable, IdMixin, UserFeedbackMixin
from app.models.tag_list import TagList


class EventPostBase(
    BaseContent, UserFeedbackMixin, Publishable, Searchable, Addressable
):
    """
    Based in part on:
    - https://microformats.org/wiki/h-event
    """

    # Inherited from BaseContent
    # - summary: short summary of the event (plain text)
    # - content: more detailed description of the event (html)

    # Event schedule (full datetime with timezone)
    start_datetime: Mapped[ArrowType | None] = mapped_column(
        ArrowType(timezone=True), info={"group": "dates"}
    )
    end_datetime: Mapped[ArrowType | None] = mapped_column(
        ArrowType(timezone=True), info={"group": "dates"}
    )

    # Classification
    # "genre" is "event_type"
    genre: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    sector: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    # Classifications partagées avec WIRE (FIL-01), facultatives.
    section: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    topic: Mapped[str] = mapped_column(default="", info={"group": "metadata"})

    # À qui l'événement s'adresse — décision `M1` du 2026-08-31. Ce sont
    # des **métadonnées**, comme le secteur ou la rubrique : elles ne
    # restreignent la visibilité de personne. Un membre qui n'a déclaré
    # ni compétence ni fonction voit exactement ce que voient les autres.
    # Les fonctions sont au niveau des **familles** (voir
    # `events/taxonomies.py`). `TagList` et non `sa.JSON` : la barre de
    # filtres les interroge en SQL, et SQLite échappe les accents dans
    # une colonne JSON, PostgreSQL non.
    competences: Mapped[list[str]] = mapped_column(
        TagList, default=list, info={"group": "metadata"}
    )
    fonctions: Mapped[list[str]] = mapped_column(
        TagList, default=list, info={"group": "metadata"}
    )

    # Ciblage par communauté (RG-03a). Liste de valeurs de
    # `CommunityEnum` ; **vide = ouvert à toutes**, ce qui préserve le
    # comportement des événements déjà publiés. Porté aussi par le
    # modèle public pour que le filtrage d'affichage se fasse sans
    # jointure.
    audience: Mapped[list[str]] = mapped_column(
        sa.JSON, default=list, info={"group": "metadata"}
    )

    # Mode de participation (MOD-01 à MOD-06).
    mode: Mapped[EventMode] = mapped_column(
        sa.Enum(EventMode),
        default=EventMode.ON_SITE,
        info={"group": "metadata"},
    )
    platform: Mapped[str] = mapped_column(default="", info={"group": "metadata"})

    # Tarif (PRX-01 à PRX-06). Prix en **centimes** ; `NULL` = pas de
    # prix. Public, contrairement à `access_details` : c'est même
    # l'information qu'un lecteur cherche avant de se déplacer.
    pricing: Mapped[EventPricing] = mapped_column(
        sa.Enum(EventPricing),
        default=EventPricing.FREE_FOR_ALL,
        info={"group": "metadata"},
    )
    price: Mapped[int | None] = mapped_column(default=None)  # centimes
    currency: Mapped[str] = mapped_column(default="EUR")

    # ORG-01 — l'organisateur, distinct de l'éditeur (ORG-02 : les deux
    # facultatifs). `foreign_keys` est obligatoire : `publisher_id`
    # pointe déjà sur la même table, et SQLAlchemy ne saurait pas quelle
    # colonne joindre.
    organiser_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey("crp_organisation.id"), nullable=True
    )
    organiser_name: Mapped[str] = mapped_column(default="")

    @declared_attr
    def organiser(cls):
        from app.models.organisation import Organisation

        return orm.relationship(Organisation, foreign_keys=[cls.organiser_id])

    @property
    def has_explicit_organiser(self) -> bool:
        """Un organisateur a-t-il été **désigné** ? (ORG-02)

        À distinguer d'`organiser_label`, qui répond toujours quelque
        chose : à vide, la cascade retombe sur l'éditeur, et l'affichage
        doit alors rester **exactement** celui d'avant le lot. Sans ce
        prédicat, chaque carte du site changerait de libellé.
        """
        return bool(self.organiser_id or self.organiser_name)

    @property
    def organiser_label(self) -> str:
        """Le nom à afficher pour l'organisateur — la cascade ORG-03.

        `organiser.name` → `organiser_name` → `publisher.name` →
        `owner.full_name`. Un seul endroit : la carte, la page de
        détail et le Business Wall doivent dire la même chose, et une
        cascade recopiée trois fois finit par diverger sur son dernier
        cran.

        Le dernier cran n'est jamais vide en pratique — un contenu a
        toujours un auteur — mais il est là parce que les trois
        premiers peuvent l'être tous les trois.
        """
        if self.organiser is not None and self.organiser.name:
            return self.organiser.name
        if self.organiser_name:
            return self.organiser_name
        if self.publisher is not None and self.publisher.name:
            return self.publisher.name
        return self.owner.full_name if self.owner else ""

    # MOD-02 — la seule donnée d'un événement réservée aux accrédités.
    # Elle est portée par le miroir parce que le rappel de la veille en
    # a besoin (NOT-13), mais **aucun gabarit public ne doit la lire** :
    # `ViewModel.__getattr__` délègue au modèle sans liste blanche,
    # donc `{{ event.access_details }}` s'afficherait partout sans
    # erreur. Rien dans le cadre ne l'empêche ; seule la relecture le
    # fait, et le test qui l'épingle.
    access_details: Mapped[str] = mapped_column(default="")

    # Annulation (ANN-03, ANN-04). Recopiée du modèle de saisie parce
    # que la liste, le calendrier et le Business Wall lisent le miroir :
    # ils doivent pouvoir barrer l'annonce sans jointure. Le statut
    # reste `PUBLIC` — l'annonce ne disparaît pas, elle se barre.
    cancelled_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str] = mapped_column(default="")
    # First part of the enven_type
    # ie:   event_type = "Business / Forum
    #       category = "business"
    category: Mapped[str] = mapped_column(default="", info={"group": "metadata"})
    language: Mapped[str] = mapped_column(default="FRE", info={"group": "metadata"})

    logo_url: Mapped[str] = mapped_column(default="")
    cover_image_url: Mapped[str] = mapped_column(default="")

    # only for compatibility with BaseContent:
    location: Mapped[str] = mapped_column(default="", info={"group": "location"})

    class Meta:
        groups: ClassVar[dict] = {
            "dates": ["start_datetime", "end_datetime"],
            "metadata": ["genre", "category", "language", "sector"],
        }

    # Also:
    # attendees
    # organizers


class EventPost(EventPostBase):
    __tablename__ = "evt_event_post"

    #: §7.2 — la pastille « Accrédité.e », renseignée par la vue liste
    #: qui charge toutes les accréditations de la page en une requête.
    #:
    #: **Déclaré** et non posé au vol : un attribut non annoncé est
    #: invisible au vérificateur de types et n'a pas de propriétaire —
    #: c'est le monkey-patching que le premier principe de
    #: `notes/lessons-learned.md` interdit.
    #:
    #: Le défaut `False` est ce que lisent tous les autres chemins de
    #: rendu — le Business Wall d'une organisation, notamment, qui ne
    #: connaît pas les accréditations du lecteur.
    #:
    #: Sans annotation : SQLAlchemy 2.0 ne mappe que ce qui est enveloppé
    #: dans `Mapped[...]`, donc rien n'est stocké ; et un `ClassVar` se
    #: lirait mais ne s'affecterait pas depuis une instance, ce que la
    #: vue liste doit précisément faire.
    is_accredited = False

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(BaseContent.id), primary_key=True
    )

    # id of the corresponding eventroom event (if any)
    eventroom_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, nullable=True
    )
    # Note: `address` is inherited from Addressable mixin via EventPostBase
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")

    # Localisation découpée **à l'écriture** (audit du 2026-09-01).
    #
    # C'étaient trois propriétés hybrides, donc six implémentations pour
    # trois notions : une en Python, une en SQL, par notion. Les
    # expressions SQL appelaient `split_part`, absent de SQLite, si bien
    # que les filtres « Département » et « Ville » ne rendaient jamais
    # rien hors PostgreSQL — sous un `except OperationalError` qui
    # rendait la panne muette.
    #
    # Dénormalisées parce que le point d'écriture est **unique** :
    # `event_receiver` recopie la localisation, et lui seul.
    code_postal: Mapped[str] = mapped_column(default="", index=True)
    departement: Mapped[str] = mapped_column(default="", index=True)
    ville: Mapped[str] = mapped_column(default="", index=True)


class AccreditationStatus(StrEnum):
    """État d'une demande d'accréditation à un événement.

    `WITHDRAWN` est un retrait par le membre — annulation de sa demande
    ou désinscription ; `REJECTED` est une décision de l'organisateur.
    Les deux sont distincts parce qu'ils ne se re-demandent pas de la
    même façon (RG-03, RG-13).
    """

    REQUESTED = auto()
    ACCEPTED = auto()
    REJECTED = auto()
    WITHDRAWN = auto()


class NotificationKind(StrEnum):
    """Ce dont un membre a déjà été prévenu, pour un événement donné."""

    REMINDER = auto()


class NotificationSent(IdMixin, Base):
    """Registre des envois — l'idempotence de `NOT-14`.

    Un rappel ne part jamais deux fois, même si la tâche périodique est
    rejouée. C'est la contrainte d'unicité qui le garantit, pas une
    lecture préalable : `IdMixin` génère la clé côté client, donc un
    SELECT-puis-INSERT laisserait deux tours concurrents passer tous
    les deux.

    `dedup_key` porte la **date parisienne de l'événement**, et non
    seulement son identifiant. Sans elle, déplacer la date tuerait
    définitivement le rappel de l'événement — alors que déplacer la
    date est précisément l'autre moitié de ce chantier.
    """

    __tablename__ = "evt_notification_sent"

    event_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey(EventPost.id, ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[NotificationKind] = mapped_column(sa.Enum(NotificationKind))
    dedup_key: Mapped[str] = mapped_column(default="")
    sent_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "event_id", "user_id", "kind", "dedup_key", name="uq_evt_notification_sent"
        ),
    )


class Accreditation(IdMixin, Base):
    """Une ligne par couple (événement, membre), dont le statut évolue.

    Remplace `evt_participation`, table de jointure sans état. Pas
    d'historique des décisions : seul le statut courant est conservé
    (décision D4 de la spécification). Une table d'audit sera ajoutée
    si un besoin de preuve apparaît.

    Le modèle ne connaît aucune règle de transition : elles vivent dans
    `events/services.py`, qui est le seul à écrire ici.
    """

    __tablename__ = "evt_accreditation"

    event_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey(EventPost.id, onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[AccreditationStatus] = mapped_column(
        sa.Enum(AccreditationStatus), default=AccreditationStatus.REQUESTED
    )

    # `requested_at` tient lieu d'horodatage de création : le mixin
    # `Timestamped` ajouterait un second champ de même sens, et c'est
    # sur celui-ci que l'écran organisateur trie.
    requested_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow
    )
    decided_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    decided_by_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey(User.id, ondelete="SET NULL"), nullable=True
    )

    event: Mapped[EventPost] = orm.relationship(EventPost, backref="accreditations")
    user: Mapped[User] = orm.relationship(User, foreign_keys=[user_id])

    __table_args__ = (
        sa.UniqueConstraint("event_id", "user_id", name="uq_evt_accreditation"),
        # Écran organisateur : WHERE event_id = ? AND status = ? ORDER BY requested_at
        sa.Index("ix_evt_accreditation_event_status", "event_id", "status"),
        # Bloc « Votre agenda » : WHERE user_id = ? AND status = 'accepted'
        sa.Index("ix_evt_accreditation_user_status", "user_id", "status"),
    )
