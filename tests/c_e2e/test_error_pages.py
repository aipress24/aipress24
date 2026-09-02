# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Jamais de page d'erreur nue.

Le déclencheur : une notification de la cloche pointant un contenu
depuis retiré. Le membre cliquait et tombait sur la page par défaut de
Werkzeug — en anglais, sans issue, et affichant le message interne de
l'exception (« Can't match id 7501006361107369984 »).

`Unauthorized` et `Forbidden` avaient chacun leur gestionnaire depuis
longtemps ; `NotFound` n'en avait aucun, et `errors/404.j2` existait
sans être branché nulle part — une seule vue le rendait à la main.

Les chemins d'API gardent la réponse standard : `/api/v1` a son propre
rendu JSON, et un client qui reçoit du HTML à la place d'un corps
d'erreur ne sait rien en faire.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.auth import User
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

#: Ce que rendait Werkzeug, et qu'on ne veut plus voir.
WERKZEUG_MARKERS = ("<title>404 Not Found</title>", "<h1>Not Found</h1>")

#: Une URL qui ne correspond à aucune route : le 404 vient du routage
#: lui-même, donc passe forcément par le gestionnaire.
#:
#: Surtout pas `/page/<slug>` : cette vue-là rend déjà `errors/404.j2`
#: à la main depuis toujours, si bien qu'un test dirigé dessus passe
#: même gestionnaire débranché — vérifié, trois de ces quatre tests le
#: faisaient dans leur première version.
MISSING_PAGE = "/il-n-y-a-vraiment-rien-ici"


def test_une_page_absente_rend_la_page_maison(client: FlaskClient) -> None:
    """Le 404 est en français, signé, et propose une issue."""
    response = client.get(MISSING_PAGE)

    assert response.status_code == 404
    body = response.data.decode()
    assert "Cette page n'existe pas, ou plus" in body
    assert 'href="/"' in body, "aucune issue proposée"
    for marker in WERKZEUG_MARKERS:
        assert marker not in body, f"page Werkzeug nue servie : {marker}"


def test_le_404_explique_le_contenu_retire(client: FlaskClient) -> None:
    """Le cas qui a motivé le ticket doit être nommé.

    Un membre qui suit une notification vers une publication dépubliée
    doit comprendre ce qui s'est passé, pas lire « Not Found ».
    """
    body = client.get(MISSING_PAGE).data.decode()

    assert "dépublié" in body
    assert "notification" in body


def test_le_404_ne_divulgue_pas_le_message_interne(db_session: Session, app) -> None:
    """`e.description` est écrit pour les logs, pas pour un lecteur.

    La page par défaut affichait « Can't match id <id> », ce qui expose
    des identifiants internes en clair.

    Il faut être connecté·e pour l'observer : le blueprint EVENTS refuse
    les visiteurs avant la vue, et le membre part alors vers la page de
    connexion — dont l'URL de retour contient l'identifiant, ce qui
    rendrait l'assertion trompeuse.
    """
    user = User(email="err404@example.com", first_name="E", last_name="R", active=True)
    db_session.add(user)
    db_session.flush()

    response = make_authenticated_client(app, user).get("/events/999999999")

    assert response.status_code == 404
    body = response.data.decode()
    assert "Can't match id" not in body
    assert "999999999" not in body


def test_l_api_garde_son_rendu_json(client: FlaskClient) -> None:
    """Un client d'API ne sait rien faire d'une page HTML.

    Le piège : un gestionnaire enregistré pour `NotFound` est plus
    spécifique que celui de l'API, enregistré pour `HTTPException`, donc
    il le court-circuite. La première version de ce correctif rendait du
    HTML sur les 404 de `/api/v1` — attrapé par
    `test_unknown_api_path_returns_json_404`.
    """
    response = client.get("/api/v1/il-n-y-a-rien-ici")

    assert response.status_code == 404
    assert response.headers["Content-Type"].startswith("application/json")
    assert response.get_json()["code"] == 404
    assert "Cette page n'existe pas" not in response.data.decode()
