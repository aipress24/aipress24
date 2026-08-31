# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""La cascade d'affichage de l'organisateur — `ORG-02`, `ORG-03`.

Trois notions étaient confondues : qui a saisi (`owner`), qui édite
(`publisher`), et qui organise. La distinction devient nécessaire dès
qu'une agence RP publie pour un client — l'éditeur est l'agence,
l'organisateur est le client.
"""

from __future__ import annotations

import pytest

from app.modules.events.models import EventPost


class _Org:
    def __init__(self, name: str) -> None:
        self.name = name


class _Owner:
    def __init__(self, full_name: str) -> None:
        self.full_name = full_name


def _event(**kw) -> EventPost:
    """Un `EventPost` non enregistré, dont on force les quatre entrées
    de la cascade."""
    post = EventPost(title="Salon")
    for key, value in kw.items():
        setattr(post, key, value)
    return post


class TestTheCascade:
    """`organiser.name` → `organiser_name` → `publisher.name` →
    `owner.full_name`, dans cet ordre."""

    def test_a_registered_organiser_wins(self) -> None:
        post = _event(
            organiser=_Org("Client SA"),
            organiser_name="Ignoré",
            publisher=_Org("Agence RP"),
            owner=_Owner("Jean Dupont"),
        )

        assert post.organiser_label == "Client SA"

    def test_then_the_free_text(self) -> None:
        """ORG-01 — un organisateur absent d'AiPRESS24."""
        post = _event(
            organiser=None,
            organiser_name="Festival de Cannes",
            publisher=_Org("Agence RP"),
            owner=_Owner("Jean Dupont"),
        )

        assert post.organiser_label == "Festival de Cannes"

    def test_then_the_publisher(self) -> None:
        """ORG-02 — à vide, l'organisateur affiché est l'éditeur, ce qui
        reproduit le comportement actuel."""
        post = _event(
            organiser=None,
            organiser_name="",
            publisher=_Org("Agence RP"),
            owner=_Owner("Jean Dupont"),
        )

        assert post.organiser_label == "Agence RP"

    def test_and_finally_the_author(self) -> None:
        """Le dernier cran n'est jamais atteint en pratique — un contenu
        a toujours un éditeur — mais il existe parce que les trois
        premiers peuvent être vides tous les trois."""
        post = _event(
            organiser=None,
            organiser_name="",
            publisher=None,
            owner=_Owner("Jean Dupont"),
        )

        assert post.organiser_label == "Jean Dupont"

    def test_an_organisation_without_a_name_falls_through(self) -> None:
        """Une organisation existe mais son nom est vide : la cascade
        continue plutôt que d'afficher un blanc."""
        post = _event(
            organiser=_Org(""),
            organiser_name="Festival de Cannes",
            publisher=_Org("Agence RP"),
            owner=_Owner("Jean Dupont"),
        )

        assert post.organiser_label == "Festival de Cannes"

    def test_everything_empty_gives_an_empty_string(self) -> None:
        post = _event(organiser=None, organiser_name="", publisher=None, owner=None)

        assert post.organiser_label == ""


class TestWhetherAnOrganiserWasDesignated:
    """`has_explicit_organiser` se distingue d'`organiser_label`, qui
    répond toujours quelque chose. Sans ce prédicat, chaque carte du
    site afficherait « Organisé par <l'éditeur> » alors que rien n'a
    changé pour elle."""

    def test_nothing_designated(self) -> None:
        post = _event(organiser_id=None, organiser_name="")

        assert not post.has_explicit_organiser

    @pytest.mark.parametrize(
        "kw",
        [
            {"organiser_id": 42, "organiser_name": ""},
            {"organiser_id": None, "organiser_name": "Festival de Cannes"},
            {"organiser_id": 42, "organiser_name": "Festival de Cannes"},
        ],
    )
    def test_something_designated(self, kw) -> None:
        assert _event(**kw).has_explicit_organiser
