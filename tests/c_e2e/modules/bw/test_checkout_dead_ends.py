# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0326 — le bouton « Procéder au paiement » dit ce qu'il fait.

Erick : « il faut appuyer plusieurs fois pour passer à Stripe (mais ça
fait un certain temps que c'est comme ça) ». Remarque glissée en passant
dans un ticket classé non-qualifié, et jamais qualifiée elle-même.

Deux causes, indépendantes de Stripe :

1. `POST /BW/checkout/<bw_type>` avait trois sorties qui renvoyaient au
   début du tunnel **sans un mot**. Vu du bouton, un retour muet ne se
   distingue pas d'un clic sans effet — donc on reclique.
2. Le formulaire était un POST nu, sans état d'envoi, alors que la
   création de la session peut enchaîner trois allers-retours Stripe.

Ces tests couvrent (1), qui est vérifiable côté serveur. Pour (2) voir
`payment.html` : `onsubmit` désarme le second envoi.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flask.testing import FlaskClient


def _flashes(client: FlaskClient) -> list[str]:
    """Les messages en attente, lus sans les consommer côté serveur."""
    with client.session_transaction() as sess:
        return [msg for _category, msg in sess.get("_flashes", [])]


def test_un_type_de_bw_inconnu_est_annonce(
    authenticated_owner_client: FlaskClient,
) -> None:
    """Sortie muette n° 1 : `bw_type` hors de `BW_TYPES`."""
    response = authenticated_owner_client.post("/BW/checkout/pas-un-type")

    assert response.status_code in (301, 302, 303)
    messages = _flashes(authenticated_owner_client)
    assert messages, "l'utilisateur est renvoyé au tunnel sans explication"
    assert any("n'existe pas" in m for m in messages)


def test_stripe_non_configure_est_annonce(
    authenticated_owner_client: FlaskClient,
    app,
    monkeypatch,
) -> None:
    """Sortie muette n° 3 : le retour de `load_stripe_api_key` était ignoré.

    Sans clé, on poursuivait jusqu'à l'échec de `Session.create`, dont le
    message générique — « Merci de réessayer » — invite précisément à
    recliquer sur une instance où ça ne marchera jamais.
    """
    monkeypatch.setitem(app.config, "STRIPE_SECRET_KEY", None)

    response = authenticated_owner_client.post("/BW/checkout/media")

    assert response.status_code in (301, 302, 303)
    messages = _flashes(authenticated_owner_client)
    assert any("n'est pas configuré" in m for m in messages), messages


def test_le_formulaire_de_paiement_desarme_le_second_envoi() -> None:
    """La cause n° 2, telle qu'elle tient dans le gabarit.

    Une assertion sur la source, et elle s'assume comme telle : le bloc
    concerné est derrière `stripe_live and stripe_public_key`, donc le
    sortir d'un rendu réel demanderait un catalogue Stripe et une session
    authentifiée pour une propriété qui est celle du fichier. Ce qu'on
    protège est qu'un remaniement ne reparte pas sur un `<form>` nu, où
    le bouton reste cliquable pendant les trois allers-retours Stripe.
    """
    source = Path(
        "src/app/modules/bw/bw_activation/templates/bw_activation/payment.html"
    ).read_text()
    form = source[source.index("bw_activation.checkout") :][:800]

    assert "onsubmit=" in form
    assert "disabled = true" in form
    assert "dataset.sent" in form


def test_choisir_une_offre_avant_est_annonce(
    authenticated_owner_client: FlaskClient,
) -> None:
    """La page de paiement renvoyait au tunnel sans dire pourquoi."""
    with authenticated_owner_client.session_transaction() as sess:
        sess.pop("pricing_value", None)

    response = authenticated_owner_client.get("/BW/payment/media")

    assert response.status_code in (301, 302, 303)
    assert any("choisir d'abord" in m for m in _flashes(authenticated_owner_client))
