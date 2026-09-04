# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0325 — un membre est présenté par sa fonction déclarée.

Erick : « je suis présentée par une expression passe-partout et assez
incommode : "Dirigeant.e d'une Entreprise de Services et Conseils en
Transformation des Organisations" ». C'est `profile_label`, le libellé
de famille du KYC. Ce qu'il veut voir est la fonction que le membre a
lui-même déclarée — `User.fonction`.

Le ticket a été livré sur l'annuaire, MARKET et le profil, mais les
cartes d'article de NEWS et le développé de l'article étaient restés sur
`job_title`, qui rend `profile_label`. Ces deux surfaces sont pinnées
ici : ce sont celles qu'Erick a rouvertes.

`job_title` garde son sens ailleurs — API publique, export admin, index
de recherche, filtre de l'annuaire — donc ces tests vérifient bien deux
propriétés distinctes et non un renommage.
"""

from __future__ import annotations

import arrow
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost
from flask import render_template_string
from markupsafe import escape

#: Ce que le KYC range sous « DIRECTION GÉNÉRALE ». La barre est la
#: séparation famille / détail : seul le détail s'affiche.
FONCTION_DECLAREE = "DIRECTION GÉNÉRALE / PDG"
DETAIL_ATTENDU = "PDG"

#: Le libellé passe-partout du KYC, celui qu'Erick récuse, mot pour mot.
LIBELLE_KYC = (
    "Dirigeant.e d'une Entreprise de Services et Conseils "
    "en Transformation des Organisations"
)
#: Le même, tel qu'il ressort du rendu : l'apostrophe passe en `&#39;`
#: sous autoescape. Comparer à la chaîne brute rendrait le test
#: complaisant — il ne matcherait jamais, dans un sens comme dans l'autre.
LIBELLE_KYC_RENDU = str(escape(LIBELLE_KYC))


def _auteur(db_session, *, avec_fonction: bool, avec_orga: bool = True):
    """Un auteur, avec ou sans fonction déclarée dans son KYC."""
    org = None
    if avec_orga:
        org = Organisation(name="Fake-Circuits courts")
        db_session.add(org)
        db_session.flush()

    user = User(email="martine@example.com", first_name="Martine", last_name="Lefebure")
    if org is not None:
        user.organisation = org
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(user_id=user.id)
    profile.profile_label = LIBELLE_KYC
    profile.match_making = (
        {"fonctions_org_priv_detail": [FONCTION_DECLAREE]} if avec_fonction else {}
    )
    db_session.add(profile)
    db_session.flush()
    db_session.refresh(user)
    return user, org


def _article(db_session, owner: User) -> ArticlePost:
    post = ArticlePost(owner=owner, title="Les circuits courts en 2026")
    post.published_at = arrow.now()
    db_session.add(post)
    db_session.flush()
    return post


def _carte(post: ArticlePost) -> str:
    return render_template_string('{{ component("post-card", c) }}', c=post)


def test_la_carte_affiche_la_fonction_declaree(db_session, app) -> None:
    """La régression : la carte montrait `profile_label`, pas la fonction."""
    with app.test_request_context():
        user, _org = _auteur(db_session, avec_fonction=True)
        post = _article(db_session, user)

        html = _carte(post)

        assert DETAIL_ATTENDU in html
        # `profile_label` est le libellé passe-partout qu'Erick récuse.
        assert LIBELLE_KYC_RENDU not in html


def test_la_carte_separe_fonction_et_organisation_par_une_barre(
    db_session, app
) -> None:
    """Le ticket demande « Fonction / Organisation », pas « @ » ni « chez »."""
    with app.test_request_context():
        user, org = _auteur(db_session, avec_fonction=True)
        post = _article(db_session, user)

        html = _carte(post)

        assert f"{DETAIL_ATTENDU} / {org.name}" in html
        assert f"{DETAIL_ATTENDU} @ " not in html
        assert " chez " not in html


def test_sans_fonction_declaree_la_carte_garde_un_sous_titre(db_session, app) -> None:
    """48 des 186 profils mesurés n'ont aucune fonction.

    `User.fonction` retombe alors sur `profile_label` : un quart des
    cartes perdrait son sous-titre sans ce repli.
    """
    with app.test_request_context():
        user, _org = _auteur(db_session, avec_fonction=False)
        post = _article(db_session, user)

        assert user.fonction == LIBELLE_KYC
        assert LIBELLE_KYC_RENDU in _carte(post)


def test_un_auteur_sans_organisation_ne_casse_pas_la_carte(db_session, app) -> None:
    """`organisation_id` est nullable — pas de barre orpheline."""
    with app.test_request_context():
        user, _ = _auteur(db_session, avec_fonction=True, avec_orga=False)
        post = _article(db_session, user)

        html = _carte(post)

        assert DETAIL_ATTENDU in html
        assert f"{DETAIL_ATTENDU} /" not in html


def test_la_ligne_publie_par_porte_la_fonction(db_session, app) -> None:
    """La mention « Publié par … » n'est pas sous la carte, ticket #0093 / #0241 (modif 4oct26)."""
    with app.test_request_context():
        user, org = _auteur(db_session, avec_fonction=True)
        post = _article(db_session, user)

        html = _carte(post)

        assert (
            f"Publié par {user.full_name}, {DETAIL_ATTENDU} / {org.name}." not in html
        )
