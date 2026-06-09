# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from enum import StrEnum, auto
from typing import ClassVar

import sqlalchemy as sa
from advanced_alchemy.types.file_object import FileObject, StoredObject
from sqlalchemy import JSON, BigInteger, Enum, ForeignKey, orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from sqlalchemy_utils import ArrowType
from sqlalchemy_utils.functions.orm import hybrid_property

from app.models.base import Base
from app.models.base_content import BaseContent
from app.models.lifecycle import PublicationStatus
from app.models.mixins import IdMixin, LifeCycleMixin, Owned, Timestamped
from app.models.organisation import Organisation
from app.services.html_sanitize import SanitizedHTML
from app.services.tagging.interfaces import Taggable

DRAFT = PublicationStatus.DRAFT


class PublisherType(StrEnum):
    AGENCY = auto()
    MEDIA = auto()
    COM = auto()  # PR agency
    OTHER = auto()


class NewsMetadataMixin:
    # NEWS-Genres
    genre: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # NEWS-Rubriques
    section: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # NEWS-Types d’info / "Thématique"
    topic: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # NEWS-Secteurs
    sector: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # Géo-localisation
    geo_localisation: Mapped[str] = mapped_column(default="", use_existing_column=True)

    # Langue
    language: Mapped[str] = mapped_column(default="fr", use_existing_column=True)

    # addressi (if any)
    address: Mapped[str] = mapped_column(default="", use_existing_column=True)
    pays_zip_ville: Mapped[str] = mapped_column(default="", use_existing_column=True)
    pays_zip_ville_detail: Mapped[str] = mapped_column(
        default="", use_existing_column=True
    )

    @hybrid_property
    def code_postal(self) -> str:
        """Return the zip code"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2]
        except IndexError:
            return ""

    @code_postal.expression
    def code_postal(cls):
        """SQL expression for the zip code property."""
        return func.coalesce(func.split_part(cls.pays_zip_ville_detail, " ", 3))

    @hybrid_property
    def departement(self) -> str:
        """Return the 2 first digit of zip code"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2][:2]
        except IndexError:
            return ""

    @departement.expression
    def departement(cls):
        """SQL expression for the departement property."""
        return func.coalesce(
            func.substring(func.split_part(cls.pays_zip_ville_detail, " ", 3), 1, 2),
            "",
        )

    @hybrid_property
    def ville(self) -> str:
        """Return the 4th part of pays_zip_ville_detail"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            data = self.pays_zip_ville_detail.split()[3]
            if data.endswith('"}'):  # fixme: origin of bad formatting in test data?
                return data[:-2]
            return data
        except IndexError:
            return ""

    @ville.expression
    def ville(cls):
        """SQL expression for the ville property."""
        part = func.split_part(cls.pays_zip_ville_detail, " ", 4)
        return func.coalesce(func.rtrim(part, '"}'), "")


class Post(NewsMetadataMixin, BaseContent, LifeCycleMixin):
    __mapper_args__: ClassVar[dict] = {
        "polymorphic_identity": "post",
    }

    title: Mapped[str] = mapped_column(default="", use_existing_column=True)
    # Re-declaring `content` here with `use_existing_column=True` would
    # silently drop the SanitizedHTML type set on the BaseContent
    # parent column. Carry the type forward so ArticlePost /
    # PressReleasePost still sanitize on write.
    content: Mapped[str] = mapped_column(
        SanitizedHTML, default="", use_existing_column=True
    )
    summary: Mapped[str] = mapped_column(default="")

    # Etat: Brouillon, Publié, Archivé
    status: Mapped[PublicationStatus] = mapped_column(
        Enum(PublicationStatus), default=DRAFT
    )

    published_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    last_updated_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    publisher_id: Mapped[int | None] = mapped_column(ForeignKey(Organisation.id))
    media_id: Mapped[int | None] = mapped_column(ForeignKey(Organisation.id))

    # Reference to first image from newsroom Article or Communique.
    # No FK because images are stored in polymorphic tables (wip_article_image,
    # wip_communique_image) depending on post type. Set by receivers.py.
    image_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Rights assignment policy — frozen at publication (DRAFT → PUBLIC).
    # Null = pre-MVP content, treated as `all_subscribed` for back-compat.
    # Shape matches `BusinessWall.rights_sales_policy`.
    rights_sales_snapshot: Mapped[dict | None] = mapped_column(
        JSON, nullable=True, default=None
    )

    @orm.declared_attr
    def publisher(cls):
        return orm.relationship(
            Organisation,
            foreign_keys=[cls.publisher_id],  # type: ignore[list-item]
        )

    @orm.declared_attr
    def media(cls):
        return orm.relationship(
            Organisation,
            foreign_keys=[cls.media_id],  # type: ignore[list-item]
        )

    # # Taille
    # taille_contenu: Mapped[str] = mapped_column(default="")


class ArticlePost(Post, Taggable):
    __mapper_args__: ClassVar[dict] = {
        "polymorphic_identity": "article",
    }

    # id of the corresponding newsroom article (if any)
    newsroom_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, nullable=True
    )

    publisher_type: Mapped[PublisherType] = mapped_column(
        Enum(PublisherType), default=PublisherType.MEDIA
    )


class PressReleasePost(Post, Taggable):
    __mapper_args__: ClassVar[dict] = {
        "polymorphic_identity": "press_release",
    }

    # id of the corresponding com'room communique (if any)
    newsroom_id: Mapped[int | None] = mapped_column(
        BigInteger, index=True, nullable=True, use_existing_column=True
    )

    publisher_type: Mapped[PublisherType] = mapped_column(
        Enum(PublisherType), default=PublisherType.COM, use_existing_column=True
    )


# --------------------------------------------------------------------------
# Article-level one-off purchases (consultation / justif / cession de droits)
# --------------------------------------------------------------------------


class PurchaseProduct(StrEnum):
    """Kinds of article-level one-off purchases.

    Matches the four buy actions on the article page (wire aside):
    - `consultation` : read-access to an otherwise truncated article.
    - `consultation_gift` : pay to grant `consultation` to N other
      members (ticket #0194 — « Consultation d'article offerte »).
      The N beneficiaries are stored in `ArticlePurchaseGift` rows
      attached to the parent purchase ; each can read the article
      in full.
    - `justificatif` : official PDF proof of publication.
    - `cession` : reproduction licence for another media.
    """

    CONSULTATION = auto()
    CONSULTATION_GIFT = auto()
    JUSTIFICATIF = auto()
    CESSION = auto()


class PurchaseStatus(StrEnum):
    PENDING = auto()
    PAID = auto()
    FAILED = auto()
    REFUNDED = auto()


class ArticlePurchase(IdMixin, Owned, Timestamped, Base):
    """One-off purchase attached to a wire Post (article or press release).

    Persisted right after Stripe Checkout success via
    `checkout.session.completed` in `mode=payment`. The "effect" of the
    purchase (access unlock, PDF generation, licence creation) is left
    to downstream specs — this model just records the transaction.
    """

    __tablename__ = "wire_article_purchase"

    # FK to the wire Post (article or press release).
    post_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("frt_content.id"), nullable=False, index=True
    )

    product_type: Mapped[PurchaseProduct] = mapped_column(
        Enum(PurchaseProduct), nullable=False
    )
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus), default=PurchaseStatus.PENDING
    )

    # Stripe references (idempotency via `stripe_checkout_session_id`).
    stripe_checkout_session_id: Mapped[str | None] = mapped_column(
        default=None, unique=True
    )
    stripe_payment_intent_id: Mapped[str | None] = mapped_column(default=None)

    amount_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    currency: Mapped[str] = mapped_column(default="EUR")

    paid_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    # Justificatif PDF (article-paywall MVP v0). Populated by the
    # Dramatiq job after a JUSTIFICATIF purchase reaches PAID. Null for
    # other product types or until generation completes.
    pdf_file: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )

    post = orm.relationship(Post, foreign_keys=[post_id])

    def pdf_signed_url(self, expires_in: int = 3600) -> str | None:
        """Return a temporary download URL for the justificatif PDF."""
        file_obj: FileObject | None = self.pdf_file
        if file_obj is None:
            return None
        try:
            return file_obj.sign(expires_in=expires_in, for_upload=False)
        except RuntimeError:
            return None


class ArticlePurchaseGift(IdMixin, Timestamped, Base):
    """Ticket #0194 — beneficiaries of a `CONSULTATION_GIFT` purchase.

    One row per (purchase, beneficiary) pair. The buyer paid for N
    beneficiaries → N rows attached to the same `ArticlePurchase`.
    Each beneficiary, once the parent purchase is PAID, can read the
    article in full (paywall lifted).

    Unique on (purchase_id, beneficiary_user_id) — a single purchase
    can't gift the same person twice.
    """

    __tablename__ = "wire_article_purchase_gift"

    purchase_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("wire_article_purchase.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    beneficiary_user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("aut_user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    notified_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    purchase = orm.relationship(
        "ArticlePurchase",
        foreign_keys=[purchase_id],
        backref=orm.backref("gifts", cascade="all, delete-orphan"),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "purchase_id",
            "beneficiary_user_id",
            name="uq_purchase_gift_beneficiary",
        ),
    )
