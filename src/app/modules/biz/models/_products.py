# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# TODO
"""
'-----------------------------------------------------------------
'Marketplace content
'-----------------------------------------------------------------

abstract class MarketplaceContent {
}
MarketplaceContent -up-|> BaseContent

class ServicesProposal {
    +valid_from DateTime
    +valid_until DateTime

    +description HTML
}
ServicesProposal -up-|> MarketplaceContent

class RFP {
    +open_from DateTime
    +open_until DateTime
    +...
}
RFP -up-|> MarketplaceContent

class ResponseToRFP {
}
ResponseToRFP -up-|> MarketplaceContent
ResponseToRFP --o RFP
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.lib.names import to_snake_case
from app.models.base import Base
from app.models.content.mixins import ClassificationMixin, Publishable
from app.models.lifecycle import PublicationStatus
from app.models.mixins import IdMixin, LifeCycleMixin, Owned

__all__ = [
    "EditorialProduct",
    "MarketplaceContent",
    # "ServicesProposal",
    # "RFP",
    # "ResponseToRFP",
]


class MarketplaceContent(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "mkp_content"

    type: Mapped[str] = mapped_column()
    status: Mapped[PublicationStatus] = mapped_column(default=PublicationStatus.DRAFT)

    @declared_attr
    def __mapper_args__(cls):
        return {
            "polymorphic_identity": to_snake_case(cls.__name__),
            "polymorphic_on": cls.type,
        }


class EditorialProduct(MarketplaceContent, ClassificationMixin, Publishable):
    __tablename__ = "mkp_editorial_product"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, ForeignKey(MarketplaceContent.id), primary_key=True
    )
    title: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
    image_url: Mapped[str] = mapped_column(default="")
    product_type: Mapped[str] = mapped_column(default="Article")
    price: Mapped[int] = mapped_column(default=0)
    """Indiquez qui est propriétaire de la production :

    - Je suis le seul propriétaire de cette production
    - Nous sommes plusieurs propriétaires (inscrits sur AIpress24)
        - déterminez les % de copropriété
    - Nom de l’Agence de presse propriétaire
    - Nom du Média propriétaire
    """

    """
    Description technique
    ...
    """


# class ServicesProposal(MarketplaceContent):
#     __tablename__ = "mkp_services_proposal"
#     _type = ContentType.service_proposal
#     __mapper_args__ = {"polymorphic_identity": _type}
#
#     id = sa.Column(sa.Integer, sa.ForeignKey(MarketplaceContent.id), primary_key=True)
#     title = sa.Column(sa.UnicodeText, nullable=False, default="")
#     description = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#     # Key dates
#     valid_from = sa.Column(sa.Date)
#     valid_until = sa.Column(sa.Date)
#
#     # TODO: shoudl be URI
#     url = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#     # Classification
#     category = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#     # Body
#     language = sa.Column(sa.Unicode(3), nullable=False, default="FRE")
#     content = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#     # Marketing
#     image_url = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#
# class RFP(MarketplaceContent):
#     __tablename__ = "mkp_rfp"
#     _type = ContentType.rfp
#     __mapper_args__ = {"polymorphic_identity": _type}
#
#     id = sa.Column(sa.Integer, sa.ForeignKey(MarketplaceContent.id), primary_key=True)
#     title = sa.Column(sa.UnicodeText, nullable=False, default="")
#     description = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#     # Key dates
#     deadline = sa.Column(ArrowType)
#
#     # TODO: shoudl be URI
#     url = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#     # Classification
#     category = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#     # Body
#     language = sa.Column(sa.Unicode(3), nullable=False, default="FRE")
#     content = sa.Column(sa.UnicodeText, nullable=False, default="")
#
#
# class ResponseToRFP(MarketplaceContent):
#     __tablename__ = "mkp_response_to_rfp"
#     _type = ContentType.response_to_rfp
#     __mapper_args__ = {"polymorphic_identity": _type}
#
#     id = sa.Column(sa.Integer, sa.ForeignKey(MarketplaceContent.id), primary_key=True)
#     # title = sa.Column(sa.UnicodeText, nullable=False, default="")
#     title = "Réponse à un RFP"
#
#     rfp_id = sa.Column(sa.Integer, sa.ForeignKey(RFP.id))
#     rfp = sa.orm.relationship(RFP, foreign_keys=[rfp_id])
