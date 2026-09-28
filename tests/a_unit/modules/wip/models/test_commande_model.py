# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0362 — a commande belongs to whoever places it.

The owner (a rédac chef or equivalent) validates or cancels it; its
destinataire, the journalist who will write it, only reads it.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.auth import User
from app.models.errors import BusinessRuleError
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import Commande

_OWNER_ID = 1
_DESTINATAIRE_ID = 2


def _commande(
    status: PublicationStatus = PublicationStatus.DRAFT,
    destinataire_id: int | None = _DESTINATAIRE_ID,
) -> Commande:
    return Commande(
        owner_id=_OWNER_ID,
        commanditaire_id=_OWNER_ID,
        destinataire_id=destinataire_id,
        status=status,
    )


class TestCommanditaire:
    def test_it_is_the_owner_whatever_commanditaire_id_says(self):
        owner = User(first_name="Eliane", last_name="Kan")
        commande = Commande(owner=owner, commanditaire_id=999)

        assert commande.commanditaire is owner


class TestVisibility:
    def test_the_owner_and_the_destinataire_see_it(self):
        commande = _commande()

        assert commande.is_visible_to(_OWNER_ID)
        assert commande.is_visible_to(_DESTINATAIRE_ID)

    def test_nobody_else_does(self):
        assert not _commande().is_visible_to(3)


class TestValidate:
    def test_a_draft_becomes_validated(self):
        commande = _commande()

        commande.validate()

        assert commande.status == PublicationStatus.ACCEPTED

    def test_it_needs_a_destinataire(self):
        commande = _commande(destinataire_id=None)

        assert not commande.can_validate()
        with pytest.raises(BusinessRuleError, match="destinataire"):
            commande.validate()
        assert commande.status == PublicationStatus.DRAFT

    @pytest.mark.parametrize(
        "status", [PublicationStatus.ACCEPTED, PublicationStatus.CANCELLED]
    )
    def test_only_a_draft_can_be_validated(self, status: PublicationStatus):
        commande = _commande(status)

        assert not commande.can_validate()
        with pytest.raises(BusinessRuleError):
            commande.validate()


class TestCancel:
    @pytest.mark.parametrize(
        "status", [PublicationStatus.DRAFT, PublicationStatus.ACCEPTED]
    )
    def test_a_draft_or_validated_commande_can_be_cancelled(
        self, status: PublicationStatus
    ):
        commande = _commande(status)

        commande.cancel()

        assert commande.status == PublicationStatus.CANCELLED

    def test_a_cancelled_commande_stays_cancelled(self):
        commande = _commande(PublicationStatus.CANCELLED)

        assert not commande.can_cancel()
        with pytest.raises(BusinessRuleError):
            commande.cancel()


class TestStatusLabel:
    @pytest.mark.parametrize(
        ("status", "label"),
        [
            (PublicationStatus.DRAFT, "Draft"),
            (PublicationStatus.ACCEPTED, "Validée"),
            (PublicationStatus.CANCELLED, "Annulée"),
        ],
    )
    def test_a_commande_is_validated_or_cancelled(
        self, status: PublicationStatus, label: str
    ):
        assert _commande(status).status_label == label


class TestMediaName:
    """The media the commande is placed for: the commanditaire's."""

    def test_it_prefers_the_business_wall_name(self):
        media = SimpleNamespace(name="Fake Agence ATS SA", bw_name="Fake Agence ATS")
        commande = SimpleNamespace(media=media)

        assert Commande.media_name.fget(commande) == "Fake Agence ATS"

    def test_it_falls_back_on_the_organisation_name(self):
        media = SimpleNamespace(name="Fake-Info Riesser", bw_name="")
        commande = SimpleNamespace(media=media)

        assert Commande.media_name.fget(commande) == "Fake-Info Riesser"

    def test_no_media_reads_empty(self):
        assert Commande.media_name.fget(SimpleNamespace(media=None)) == ""
