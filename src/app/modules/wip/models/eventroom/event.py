# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

import arrow
import sqlalchemy as sa
from advanced_alchemy.types.file_object import FileObject, StoredObject
from sqlalchemy import event as sa_event, orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.enums import MODE_LABELS, PRICING_LABELS, EventMode, EventPricing
from app.lib.file_object_utils import media_url
from app.models.base import Base
from app.models.errors import BusinessRuleError
from app.models.lifecycle import PublicationStatus
from app.models.mixins import IdMixin, LifeCycleMixin, Owned
from app.models.organisation import Organisation
from app.models.tag_list import TagList
from app.services.html_sanitize import SanitizedHTML

DRAFT = PublicationStatus.DRAFT


class Event(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "evr_event"

    # from LifeCycleMixin:
    # created_at...
    # modified_at...
    # deleted_at...

    # from Owned:
    # owner_id...
    # owner...

    # Contenu — Trix-rendered HTML; sanitize on write.
    chapo: Mapped[str] = mapped_column(default="")
    contenu: Mapped[str] = mapped_column(SanitizedHTML, default="")

    # Etat: Brouillon, Publié, Archivé...
    status: Mapped[PublicationStatus] = mapped_column(
        sa.Enum(PublicationStatus), default=DRAFT
    )

    #
    # Publication dates
    #
    published_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    #
    # Specific metadata
    #
    #: where the event takes place
    #
    # location: Mapped[str] = mapped_column(default="", info={"group": "location"})

    start_time: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    end_time: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    #
    # Organisation
    #
    publisher_id: Mapped[int] = mapped_column(
        sa.ForeignKey(Organisation.id), nullable=True
    )
    publisher: Mapped[Organisation] = orm.relationship(
        Organisation, foreign_keys=[publisher_id]
    )

    # ORG-01 — l'organisateur, distinct de l'éditeur. Une agence RP
    # publie pour son client : l'éditeur est l'agence, l'organisateur
    # est le client. Les deux champs sont facultatifs (ORG-02) ; à
    # vide, l'organisateur affiché reste l'éditeur, ce qui reproduit le
    # comportement actuel.
    #
    # `organiser_id` quand l'organisateur est inscrit sur AiPRESS24,
    # `organiser_name` en texte libre sinon.
    organiser_id: Mapped[int | None] = mapped_column(
        sa.ForeignKey(Organisation.id), nullable=True
    )
    organiser: Mapped[Organisation | None] = orm.relationship(
        Organisation, foreign_keys=[organiser_id]
    )
    organiser_name: Mapped[str] = mapped_column(default="")

    #
    # Content
    #
    titre: Mapped[str] = mapped_column(default="")

    #
    # Classification
    #

    # Type d'événement
    event_type: Mapped[str] = mapped_column(default="")

    # NEWS-Secteurs
    sector: Mapped[str] = mapped_column(default="")

    # Mêmes noms et mêmes vocabulaires que WIRE (FIL-01) : `section`
    # vient de la feuille d'ontologie « Rubriques », `topic` de
    # « Type d'info ». Facultatifs (FIL-02) — les rendre obligatoires
    # invaliderait les événements déjà saisis.
    section: Mapped[str] = mapped_column(default="")
    topic: Mapped[str] = mapped_column(default="")

    # À qui l'événement s'adresse — décision `M1` du 2026-08-31. Ce sont
    # des **métadonnées**, comme le secteur ou la rubrique : elles ne
    # restreignent la visibilité de personne. Un membre qui n'a déclaré
    # ni compétence ni fonction voit exactement ce que voient les autres.
    # Les fonctions sont au niveau des **familles** (voir
    # `events/taxonomies.py`). `TagList` et non `sa.JSON` : la barre de
    # filtres les interroge en SQL, et SQLite échappe les accents dans
    # une colonne JSON, PostgreSQL non.
    competences: Mapped[list[str]] = mapped_column(TagList, default=list)
    fonctions: Mapped[list[str]] = mapped_column(TagList, default=list)

    # Ciblage par communauté — vide = ouvert à toutes (RG-03a).
    audience: Mapped[list[str]] = mapped_column(sa.JSON, default=list)

    # Annulation (ANN-03). Deux colonnes plutôt qu'une valeur de plus
    # dans `PublicationStatus` : un événement annulé **reste `PUBLIC`**,
    # c'est ce qui permet de continuer à l'afficher barré au lieu de le
    # faire disparaître, sans toucher à une énumération que partagent
    # tous les contenus.
    # Annoté `arrow.Arrow` et non `datetime` — contrairement à ses
    # voisines, qui mentent sur ce qu'`ArrowType` rend et paient ce
    # mensonge d'un `type: ignore` à chaque affectation.
    cancelled_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    cancellation_reason: Mapped[str] = mapped_column(default="")

    # Motif du dernier renvoi de relecture (décision `C9-b`). Porté par
    # `evr_event` seul : un événement renvoyé est un brouillon, et le
    # miroir public n'a jamais à en connaître.
    send_back_reason: Mapped[str] = mapped_column(default="")

    # Mode de participation (MOD-01). `platform` est un champ libre et
    # non une ontologie (MOD-06) : la liste des outils de
    # visioconférence change trop vite pour valoir une taxonomie, et
    # aucun besoin de filtrage dessus n'est exprimé.
    mode: Mapped[EventMode] = mapped_column(
        sa.Enum(EventMode), default=EventMode.ON_SITE
    )
    platform: Mapped[str] = mapped_column(default="")
    # MOD-02 — réservé aux personnes accréditées. C'est la seule donnée
    # d'un événement soumise à ce régime : ni la liste, ni un visiteur
    # non accrédité, ni l'index de recherche ne doivent la voir.
    access_details: Mapped[str] = mapped_column(default="")

    # Tarif (PRX-01). `price` est en **centimes**, comme les budgets de
    # `biz/models/_offers.py` : aucun montant ne transite en flottant.
    # `NULL` veut dire « pas de prix », ce qui est le cas de tout
    # événement gratuit pour tout le monde (PRX-03).
    pricing: Mapped[EventPricing] = mapped_column(
        sa.Enum(EventPricing), default=EventPricing.FREE_FOR_ALL
    )
    price: Mapped[int | None] = mapped_column(default=None)  # centimes
    currency: Mapped[str] = mapped_column(default="EUR")

    # Localisation
    address: Mapped[str] = mapped_column(default="")
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")

    url: Mapped[str] = mapped_column(default="")

    # Langue
    language: Mapped[str] = mapped_column(default="fr")

    # Image list
    images: ClassVar[list[EventImage]]

    # Temp hack
    @property
    def title(self):
        return self.titre

    # ------------------------------------------------------------
    # Business Logic - Publication Workflow
    # ------------------------------------------------------------

    def set_schedule(self, start: datetime, end: datetime) -> None:
        """
        Set the event schedule (start and end times).

        Args:
            start: Event start datetime
            end: Event end datetime

        Raises:
            BusinessRuleError: If end time is before start time
        """
        # Handle timezone-naive datetimes by adding UTC
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)

        if end < start:
            msg = "end_time must be after start_time"
            raise BusinessRuleError(msg)

        self.start_time = start
        self.end_time = end

    def can_publish(self) -> bool:
        """Check if event can be published.

        Depuis REL-01, un événement peut être publié depuis un brouillon
        **ou** depuis la relecture : le cycle est
        `DRAFT → PENDING → PUBLIC`, et `DRAFT → PUBLIC` reste ouvert à un
        rôle habilité qui se passe de relecture.
        """
        return self.status in (PublicationStatus.DRAFT, PublicationStatus.PENDING)

    def check_publishable(self) -> None:
        """Les règles qu'un événement **publié** ne doit jamais violer.

        Extraites de `publish()` pour être rejouables ailleurs : à
        l'édition d'un événement publié — sans quoi un organisateur
        pouvait publier un événement valide puis le modifier vers un
        état que la publication aurait refusé, et cet état partait sur
        la carte — et à la **soumission** en relecture (REL-04), pour
        qu'un relecteur n'hérite jamais d'un brouillon impubliable.

        Les règles gouvernent l'état publié, pas l'instant de la
        publication. Un brouillon reste librement incomplet : c'est ce
        qu'est un brouillon.

        Raises:
            BusinessRuleError: un champ requis manque.
        """
        if not self.titre or not self.titre.strip():
            msg = "Cannot publish event: titre is required"
            raise BusinessRuleError(msg)

        if not self.contenu or not self.contenu.strip():
            msg = "Cannot publish event: contenu is required"
            raise BusinessRuleError(msg)

        # Bug #0172 — un événement sans dates serait silencieusement
        # écarté de la liste publique (le filtre par défaut compare
        # `start_datetime`/`end_datetime` à aujourd'hui, et `NULL >=
        # today` vaut `NULL`, donc faux). Refuser à la publication avec
        # un message clair, plutôt que de le rendre invisible.
        if not self.start_time or not self.end_time:
            msg = (
                "Cannot publish event: la date de début et la date de "
                "fin sont obligatoires pour publier un événement."
            )
            raise BusinessRuleError(msg)

        self._require_dates_in_order()
        self._require_fields_for_mode()
        self._settle_price()

    def _require_dates_in_order(self) -> None:
        """La fin ne précède pas le début."""
        start, end = self.start_time, self.end_time
        if start is None or end is None:
            return
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)
        if end < start:
            msg = "Cannot publish event: end_time must be after start_time"
            raise BusinessRuleError(msg)

    def publish(self, publisher_id: int | None = None) -> None:
        """
        Publish the event.

        Args:
            publisher_id: Optional publisher organization ID

        Raises:
            BusinessRuleError: If event cannot be published or validation fails
        """
        if not self.can_publish():
            msg = "Cannot publish event: event is not in DRAFT status"
            raise BusinessRuleError(msg)

        self.check_publishable()

        # Update state
        self.status = PublicationStatus.PUBLIC  # type: ignore[assignment]
        if not self.published_at:
            self.published_at = arrow.now("Europe/Paris")  # type: ignore[assignment]
        if publisher_id:
            self.publisher_id = publisher_id

    #: MOD-01 — ce que chaque mode exige pour être publiable, et le
    #: nom du champ tel que le formulaire le montre. Une table plutôt
    #: qu'une cascade de `if` : la règle est un tableau dans la
    #: spécification, elle se relit mieux comme un tableau ici.
    REQUIRED_BY_MODE: ClassVar[dict[EventMode, tuple[tuple[str, str], ...]]] = {
        EventMode.ON_SITE: (("address", "l'adresse de l'événement"),),
        EventMode.ONLINE: (
            ("url", "l'URL de l'événement"),
            ("platform", "la plateforme"),
        ),
        EventMode.HYBRID: (
            ("address", "l'adresse de l'événement"),
            ("url", "l'URL de l'événement"),
            ("platform", "la plateforme"),
        ),
        EventMode.PHONE: (
            ("access_details", "les modalités d'accès (numéro et code)"),
        ),
    }

    def _require_fields_for_mode(self) -> None:
        """MOD-01 — refuser la publication s'il manque un champ du mode.

        Même garde-fou que les dates du bug #0172, et pour la même
        raison : un événement en présentiel sans adresse, ou en
        distanciel sans lien, est publié mais inutilisable. Mieux vaut
        un refus explicite qu'une annonce à laquelle personne ne peut
        se rendre.

        Raises:
            BusinessRuleError: un champ requis par le mode est vide.
        """
        # Lié localement et **annoté** : `pyrefly` ne comprend pas
        # SQLAlchemy et voit un `InstrumentedAttribute[EventMode]` là où
        # le descripteur rend un `EventMode`. L'annotation dit ce qui
        # est vrai, plutôt que de museler un code d'erreur entier.
        mode: EventMode = self.mode

        missing = [
            label
            for field, label in self.REQUIRED_BY_MODE[mode]
            if not (getattr(self, field) or "").strip()
        ]
        if not missing:
            return

        # Formulé sans accord : le nombre du verbe dépendrait du
        # nombre de champs manquants, celui de l'article du libellé de
        # chacun, et les deux se contredisent — « les modalités d'accès
        # est obligatoire ». Une liste n'a pas ce problème.
        msg = (
            f"Impossible de publier : pour un événement "
            f"{MODE_LABELS[mode]}, il manque {', '.join(missing)}."
        )
        raise BusinessRuleError(msg)

    #: Tarifs qui exigent un prix pour être publiés (PRX-02).
    PRICED = (EventPricing.FREE_FOR_JOURNALISTS, EventPricing.PAID)

    def _settle_price(self) -> None:
        """Arrêter le prix à la publication (PRX-02, PRX-03).

        Deux règles inséparables, d'où une seule méthode : un tarif
        payant exige un prix strictement positif, et un tarif gratuit
        pour tout le monde n'en garde aucun — même si le formulaire en
        portait un, ce qui arrive dès qu'on saisit un montant puis
        qu'on repasse le tarif à « gratuit ».

        Raises:
            BusinessRuleError: tarif payant sans prix, ou prix négatif ou nul.
        """
        pricing: EventPricing = self.pricing
        if pricing == EventPricing.FREE_FOR_ALL:
            self.price = None
            return

        if not self.price or self.price <= 0:
            msg = (
                "Impossible de publier : un événement "
                f"« {PRICING_LABELS[pricing].lower()} » demande un prix."
            )
            raise BusinessRuleError(msg)

    # ------------------------------------------------------------
    # Business Logic - Relecture éditoriale (REL-01, REL-02, REL-04)
    # ------------------------------------------------------------

    def can_submit_for_review(self) -> bool:
        """REL-01 — seul un brouillon part en relecture."""
        return self.status == PublicationStatus.DRAFT

    def submit_for_review(self) -> None:
        """Soumettre le brouillon à la relecture de l'organisation.

        REL-04 : les mêmes contrôles qu'à la publication s'appliquent
        ici. Un relecteur ne doit jamais hériter d'un brouillon
        impubliable — il n'aurait alors le choix qu'entre le renvoyer
        pour un défaut que l'auteur ne voyait pas, ou le valider vers un
        échec.

        Raises:
            BusinessRuleError: événement pas en brouillon, ou incomplet.
        """
        if not self.can_submit_for_review():
            msg = "Impossible de soumettre à relecture : seul un brouillon peut l'être."
            raise BusinessRuleError(msg)

        self.check_publishable()
        self.status = PublicationStatus.PENDING  # type: ignore[assignment]
        # Le motif appartient au tour de relecture qui vient de s'achever :
        # le laisser montrerait au relecteur suivant un reproche déjà traité.
        self.send_back_reason = ""

    def can_send_back(self) -> bool:
        """REL-02 — seul un événement en relecture se renvoie."""
        return self.status == PublicationStatus.PENDING

    def send_back(self, comment: str) -> None:
        """Renvoyer l'événement à son auteur, avec un motif (REL-02).

        Le commentaire est **obligatoire** : un renvoi sans motif ne
        dit pas à l'auteur ce qu'il doit corriger, et le fait
        recommencer à l'aveugle.

        Il part dans la notification (NOT-07) **et** reste sur le
        brouillon, décision `C9-b` du 2026-08-31 : un auteur qui rouvrait
        son brouillon le lendemain ne le retrouvait que dans sa cloche,
        et corrigeait de mémoire. `submit_for_review` l'efface au tour
        suivant.

        Raises:
            BusinessRuleError: événement pas en relecture, ou motif vide.
        """
        if not self.can_send_back():
            msg = "Impossible de renvoyer cet événement : il n'est pas en relecture."
            raise BusinessRuleError(msg)

        if not comment.strip():
            msg = "Le motif du renvoi est obligatoire."
            raise BusinessRuleError(msg)

        self.send_back_reason = comment.strip()
        self.status = PublicationStatus.DRAFT  # type: ignore[assignment]

    def can_unpublish(self) -> bool:
        """Check if event can be unpublished."""
        return bool(self.status == PublicationStatus.PUBLIC)

    def unpublish(self) -> None:
        """
        Unpublish the event (return to DRAFT status).

        Raises:
            BusinessRuleError: If event cannot be unpublished
        """
        if not self.can_unpublish():
            msg = "Cannot unpublish event: event is not PUBLIC"
            raise BusinessRuleError(msg)

        self.status = PublicationStatus.DRAFT  # type: ignore[assignment]
        # Dépublier retire l'annonce entièrement : l'annulation n'a plus
        # d'objet, et le brouillon repart propre. Sans cet effacement,
        # une republication ressusciterait un événement affiché barré,
        # avec un `cancelled_at` trop vieux pour être rétabli (ANN-07) —
        # un état dont plus rien ne permet de sortir. Le miroir, lui, se
        # remet à jour tout seul : `on_publish_event` recopie tous les
        # champs.
        self.cancelled_at = None
        self.cancellation_reason = ""

    # ------------------------------------------------------------
    # Business Logic - Annulation (ANN-01, ANN-03, ANN-07)
    # ------------------------------------------------------------

    #: ANN-07 — le rétablissement reste possible pendant ce délai.
    #: Au-delà, l'annulation est un fait public déjà notifié, et on
    #: n'efface pas silencieusement un message déjà reçu :
    #: l'organisateur crée un nouvel événement.
    RESTORE_WINDOW_HOURS: ClassVar[int] = 24

    #: ANN-02 — le motif est facultatif et court : il tient dans un
    #: bandeau, pas dans un communiqué.
    MAX_CANCELLATION_REASON: ClassVar[int] = 280

    def can_cancel(self) -> bool:
        """ANN-01 — seul un événement publié et non déjà annulé."""
        return self.status == PublicationStatus.PUBLIC and self.cancelled_at is None

    def cancel(self, reason: str = "", now: arrow.Arrow | None = None) -> None:
        """Annuler l'événement (ANN-03).

        Ne touche ni au statut, ni aux accréditations (RG-12) :
        l'annonce reste publique, barrée, et les accrédités gardent
        leur ligne — c'est ce qui permet de les prévenir, et de
        rétablir l'événement sans avoir à les réinviter.

        `now` est un paramètre parce que ANN-07 rend le rétablissement
        dépendant de l'heure, et que ce dépôt ne sait pas geler le
        temps.

        Raises:
            BusinessRuleError: événement non publié, déjà annulé, ou motif trop long.
        """
        if not self.can_cancel():
            msg = (
                "Impossible d'annuler cet événement : il n'est pas publié, "
                "ou il est déjà annulé."
            )
            raise BusinessRuleError(msg)

        reason = reason.strip()
        if len(reason) > self.MAX_CANCELLATION_REASON:
            msg = (
                "Le motif d'annulation ne peut pas dépasser "
                f"{self.MAX_CANCELLATION_REASON} signes."
            )
            raise BusinessRuleError(msg)

        self.cancelled_at = now or arrow.utcnow()
        self.cancellation_reason = reason

    def can_restore(self, now: arrow.Arrow | None = None) -> bool:
        """ANN-07 — le rétablissement est-il encore dans la fenêtre ?"""
        if self.cancelled_at is None:
            return False
        deadline = self.cancelled_at.shift(hours=self.RESTORE_WINDOW_HOURS)
        return (now or arrow.utcnow()) <= deadline

    def restore(self, now: arrow.Arrow | None = None) -> None:
        """Rétablir un événement annulé, dans les 24 heures (ANN-07).

        Raises:
            BusinessRuleError: événement non annulé, ou fenêtre expirée.
        """
        if self.cancelled_at is None:
            msg = "Impossible de rétablir cet événement : il n'est pas annulé."
            raise BusinessRuleError(msg)
        if not self.can_restore(now):
            msg = (
                "Impossible de rétablir cet événement : l'annulation date de "
                f"plus de {self.RESTORE_WINDOW_HOURS} heures et a déjà été "
                "annoncée. Créez un nouvel événement."
            )
            raise BusinessRuleError(msg)

        self.cancelled_at = None
        self.cancellation_reason = ""

    # ------------------------------------------------------------
    # Query Methods (for templates/views)
    # ------------------------------------------------------------

    @property
    def is_draft(self) -> bool:
        """Check if event is in draft status."""
        return bool(self.status == PublicationStatus.DRAFT)

    @property
    def is_public(self) -> bool:
        """Check if event is published."""
        return bool(self.status == PublicationStatus.PUBLIC)

    @property
    def is_expired(self) -> bool:
        """Check if event has expired."""
        if not self.expired_at:
            return False

        now = datetime.now(UTC)
        # Handle timezone-naive datetime
        expired_at = self.expired_at
        if expired_at.tzinfo is None:
            expired_at = expired_at.replace(tzinfo=UTC)
        return bool(expired_at < now)

    #
    # Images management
    #
    def get_image(self, image_id: int) -> EventImage | None:
        return next((image for image in self.images if image.id == image_id), None)

    @property
    def sorted_images(self) -> list[EventImage]:
        return sorted(self.images, key=lambda x: x.position)

    def add_image(self, image: EventImage) -> None:
        self.images.append(image)
        image.position = len(self.images) - 1

    def delete_image(self, image: EventImage) -> None:
        self.images.remove(image)
        self.update_image_positions()

    def update_image_positions(self) -> None:
        for i, image in enumerate(self.sorted_images):
            image.position = i


@sa_event.listens_for(Event, "init")
def _default_enums(target, _args, kwargs) -> None:
    """Donner ses valeurs par défaut à un événement dès sa construction.

    Le `default=` de `mapped_column` n'est posé qu'à l'insertion : avant
    le premier flush, `Event().mode` vaut `None`, et les validations de
    MOD-01 et PRX-02 n'ont alors aucune ligne à consulter. Ce n'est pas
    un détail de test — l'API construit un événement et le publie dans
    la même transaction, sans flush intermédiaire.

    Le statut souffre du même défaut et s'en tire par accident :
    `can_publish()` compare `None` à `DRAFT`, ce qui est faux, et refuse
    avec un message clair. On ne peut pas compter là-dessus pour une
    table indexée par la valeur.
    """
    kwargs.setdefault("mode", EventMode.ON_SITE)
    kwargs.setdefault("pricing", EventPricing.FREE_FOR_ALL)
    # `currency` aussi : le récepteur recopie `info.currency` tel quel
    # vers une colonne `NOT NULL` du miroir, et l'API construit puis
    # publie sans flush intermédiaire.
    kwargs.setdefault("currency", "EUR")
    # Les deux motifs sont annotés `str`, pas `str | None` : sans cela
    # un brouillon non flushé les rend `None`, et l'affichage comme les
    # tests voient un type que le modèle ne déclare pas.
    kwargs.setdefault("cancellation_reason", "")
    kwargs.setdefault("send_back_reason", "")
    # Annotées `list[str]` : sans amorce, un brouillon non flushé les
    # rend `None`, et le formulaire itère alors sur rien du tout.
    kwargs.setdefault("competences", [])
    kwargs.setdefault("fonctions", [])


class EventImage(IdMixin, LifeCycleMixin, Owned, Base):
    """Images liées au Event (carousel)."""

    __tablename__ = "evr_image"

    content: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )

    event_id: Mapped[int] = mapped_column(
        sa.ForeignKey(Event.id, ondelete="CASCADE"), nullable=False
    )
    caption: Mapped[str] = mapped_column(default="")
    copyright: Mapped[str] = mapped_column(default="")

    event: Mapped[Event] = orm.relationship(
        Event, foreign_keys=[event_id], backref="images"
    )

    position: Mapped[int] = mapped_column(default=0)

    @property
    def url(self) -> str:
        return media_url(self.content)

    @property
    def is_first(self) -> bool:
        return self.position == 0

    @property
    def is_last(self) -> bool:
        return self.position == len(self.event.images) - 1
