# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0353 — who a commande is addressed to depends on its birth.

The screen showed `media_id` under the label « Commande adressée à ».
On a commande born from an accepted sujet that column holds the media
the *accepter* belongs to, so the head of TCA read « adressée à TCA »
about an order she had just placed with someone else.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.modules.wip.models import Commande


def _commande(*, owner_id, commanditaire_id, owner=None, media=None) -> SimpleNamespace:
    """A duck-typed stand-in: `addressed_to` reads four attributes and
    touches no session."""
    stub = SimpleNamespace(
        owner_id=owner_id,
        commanditaire_id=commanditaire_id,
        owner=owner,
        media=media,
    )
    return stub


_AICHA = SimpleNamespace(full_name="Aïcha Benmahfoud")
_TCA = SimpleNamespace(name="TECHNO-CHRONIQUEURS ASSOCIÉS")


class TestBornFromAnAcceptedSujet:
    """`owner_id != commanditaire_id` is the signature: `sujet_accept`
    puts the proposing journalist in `owner_id` and the accepter in
    `commanditaire_id` (bug #0225)."""

    def test_it_names_the_journalist_who_will_write_it(self):
        commande = _commande(
            owner_id=1, commanditaire_id=2, owner=_AICHA, media=_TCA
        )

        assert Commande.addressed_to.fget(commande) == "Aïcha Benmahfoud"

    def test_it_does_not_name_the_accepter_s_own_media(self):
        """The defect, stated as a test."""
        commande = _commande(
            owner_id=1, commanditaire_id=2, owner=_AICHA, media=_TCA
        )

        assert Commande.addressed_to.fget(commande) != _TCA.name


class TestCreatedDirectly:
    """`_base` puts the creator in both columns, and the order is
    addressed to the media picked on the form."""

    def test_it_names_the_media(self):
        commande = _commande(
            owner_id=7, commanditaire_id=7, owner=_AICHA, media=_TCA
        )

        assert Commande.addressed_to.fget(commande) == _TCA.name


class TestMissingRelations:
    def test_no_media_and_no_author_reads_empty(self):
        commande = _commande(owner_id=7, commanditaire_id=7, owner=None, media=None)

        assert Commande.addressed_to.fget(commande) == ""

    def test_a_sujet_born_commande_without_author_falls_back_to_the_media(self):
        """`owner` is NOT NULL, so this is defence against a detached
        instance rather than a real state — it must not raise."""
        commande = _commande(owner_id=1, commanditaire_id=2, owner=None, media=_TCA)

        assert Commande.addressed_to.fget(commande) == _TCA.name
