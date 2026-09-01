# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le blueprint WIRE est fermé aux visiteurs — sentinelle, 2026-09-02.

`app/modules/wire/__init__.py` lève `Unauthorized` dans son
`before_request`. Quatre vues d'achat refaisaient ce contrôle, et une
cinquième — `_get_purchase_or_404` — l'écrivait à l'envers : elle
*exemptait* l'anonyme du contrôle de propriété au lieu de le refuser.
Les quatre doublons sont partis et la condition inversée est redressée,
ce qui laisse `before_request` seul en charge.

Ce fichier est la sentinelle qui va avec : si la garde disparaît, ce
n'est plus une redondance qui saute, c'est l'accès qui s'ouvre — sur
`/wire/purchase/<id>/success`, dont les identifiants sont des entiers
séquentiels.
"""

from __future__ import annotations

import pytest

from app.modules.wire import blueprint

# Une URL par forme de vue : liste, détail d'achat, modale de prix,
# POST d'achat. Toutes doivent renvoyer un visiteur vers l'accueil ou
# la connexion, jamais un corps de page.
URLS_GET = [
    "/wire/",
    "/wire/purchase/1/success",
    "/wire/purchase/1/cancel",
    "/wire/1/buy_modal/consultation",
    "/wire/1/buy_modal_gift",
]
URLS_POST = [
    "/wire/1/buy/consultation",
    "/wire/1/buy_gift",
]


@pytest.mark.parametrize("url", URLS_GET)
def test_un_visiteur_n_atteint_aucune_vue_wire(client, url) -> None:
    response = client.get(url)

    assert response.status_code in (301, 302, 401), (
        f"{url} a répondu {response.status_code} à un anonyme"
    )


@pytest.mark.parametrize("url", URLS_POST)
def test_ni_par_un_post(client, url) -> None:
    response = client.post(url, data={})

    assert response.status_code in (301, 302, 401), (
        f"{url} a répondu {response.status_code} à un anonyme"
    )


def test_la_garde_est_bien_dans_le_before_request() -> None:
    """Le test ci-dessus passerait aussi si chaque vue se gardait seule.

    Ce qu'on veut affirmer, c'est que la garde est **unique et
    centralisée** : c'est elle qui autorise les vues à traiter `g.user`
    comme un membre identifié.
    """
    noms = [f.__name__ for f in blueprint.deferred_functions]
    assert blueprint.before_request_funcs or noms, (
        "le blueprint WIRE n'enregistre plus de before_request"
    )
