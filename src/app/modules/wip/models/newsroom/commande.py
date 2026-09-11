# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column

from app.models.auth import User
from app.models.base import Base
from app.models.lifecycle import PublicationStatus

from ._base import CiblageMixin, NewsMetadataMixin, NewsroomCommonMixin


class Commande(
    NewsroomCommonMixin,
    NewsMetadataMixin,
    CiblageMixin,
    Base,
):
    __tablename__ = "nrm_commande"

    @orm.declared_attr
    def commanditaire(cls):
        """Qui a passé la commande.

        La colonne `commanditaire_id` existait sans sa relation, alors
        que `owner` et `media` ont la leur : tout appelant voulant la
        personne devait la requêter à la main, et l'écran ne la
        montrait pas du tout.
        """
        return orm.relationship(User, foreign_keys=cast(Any, [cls.commanditaire_id]))

    @property
    def addressed_to(self) -> str:
        """À qui la commande est adressée, telle qu'on l'affiche.

        Ticket #0353. Deux naissances, deux destinataires :

        - née d'un **sujet accepté**, elle s'adresse au journaliste qui
          l'a proposé et qui l'écrira. `sujet_accept` le met dans
          `owner_id` (bug #0225) et met celui qui accepte dans
          `commanditaire_id` : les deux diffèrent, et c'est la
          signature de cette naissance ;
        - **créée directement**, `_base` pose le créateur dans les deux
          colonnes ; elle s'adresse alors au média choisi au
          formulaire.

        Sans cette distinction, l'écran affichait `media_id` dans les
        deux cas — donc, pour un sujet accepté, l'organisation de
        celui-là même qui accepte : « commande adressée à TCA » lue par
        la directrice de TCA.
        """
        if self.owner_id != self.commanditaire_id and self.owner:
            return self.owner.full_name
        return self.media.name if self.media else ""

    # Workflow: DRAFT → PENDING (validated) → PUBLIC (published)
    # Can also be: REJECTED, ARCHIVED

    # ------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------

    # Limite de validité
    date_limite_validite: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    # Bouclage
    date_bouclage: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    # Parution prévue
    date_parution_prevue: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    # Paiement. Nullable depuis #0343 : la date de paiement n'est pas
    # connue à la commande — « c'est un problème récurrent dans notre
    # profession ». Le champ a quitté le formulaire ; la colonne reste
    # pour les commandes qui en portent déjà une.
    date_paiement: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None
    )

    status: Mapped[PublicationStatus] = mapped_column(
        sa.Enum(PublicationStatus), default=PublicationStatus.DRAFT
    )

    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")
