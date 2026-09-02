# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le balisage de la cloche, tel que le script Playwright le cible.

`tests-e2e/test_03_notifications.py` rejoue le bug #0319 — une
notification dont la cible tombe en erreur — en pilotant un vrai
navigateur. Ce script ne tourne pas en intégration continue : il lui
faut un serveur de développement avec `UNSECURE=True`.

D'où ce fichier. Si l'en-tête change et que les sélecteurs ne trouvent
plus rien, le script ne tombe pas en échec : il rapporte « aucune
notification » et **passe**. Un test vert qui n'a rien vérifié est pire
que pas de test — `notes/lessons-learned.md`, « "Status 200" is not
"rendered correctly" ».

C'est donc le contrat entre le balisage et le script. S'il casse, c'est
le script Playwright qu'il faut corriger, pas ce test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from bs4 import BeautifulSoup
from flask import g
from svcs.flask import container

from app.models.auth import User
from app.services.notifications import NotificationService
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

#: **Les sélecteurs du script Playwright, mot pour mot.** Ils sont
#: évalués ici sur le HTML rendu, et non cherchés comme sous-chaînes :
#: `x-ref="button"` apparaît dans dix gabarits, dont deux autres rendus
#: sur cette même page. Une première version de ce test cherchait la
#: sous-chaîne et passait encore après avoir renommé l'attribut dans
#: l'en-tête — elle ne vérifiait rien. C'est le composé qui compte : un
#: conteneur portant à la fois le bouton et les formulaires.
BELL = 'div.indicator:has(form[action*="/notifications/"])'
BELL_BUTTON = f'{BELL} button[x-ref="button"]'
NOTIFICATION_FORM = 'form[action*="/notifications/"][action$="/read"]'
NOTIFICATION_BUTTON = f"{BELL} {NOTIFICATION_FORM} button"

#: Le marqueur par lequel le script isole le cas #0319 parmi les autres
#: notifications, tel que `events/notifications.py` (NOT-03) le rédige.
REJECTION_MARKER = "n'a pas été retenue"

#: L'adresse que porte la notification de test.
TARGET_URL = "/events/42"


def _bell_page(db_session: Session, app) -> BeautifulSoup:
    """Une page privée rendue pour un membre qui a une notification."""
    user = User(email="cloche@example.com", first_name="H", last_name="T", active=True)
    db_session.add(user)
    db_session.flush()

    with app.test_request_context():
        g.user = user
        container.get(NotificationService).post(
            user,
            f"Votre demande d'accréditation à l'événement « X » {REJECTION_MARKER}.",
            url=TARGET_URL,
        )
    db_session.commit()

    response = make_authenticated_client(app, user).get("/wire/tab/wall")
    assert response.status_code == 200
    return BeautifulSoup(response.data.decode(), "html.parser")


def test_le_script_sait_designer_la_cloche(db_session, app) -> None:
    """Le sélecteur qui distingue la cloche des autres menus déroulants.

    La macro `simple_dropdown` donne le même intitulé masqué (« Open
    user menu ») au bouton de la cloche et à celui du profil ; le script
    la reconnaît donc à ce qu'elle contient. Si ce composé ne rend plus
    rien, le script ouvre le mauvais menu — ou aucun — et ne voit aucune
    notification.
    """
    page = _bell_page(db_session, app)

    assert len(page.select(BELL_BUTTON)) == 1, (
        f"`{BELL_BUTTON}` ne désigne plus rien : le script Playwright "
        f"ouvrira le vide et rapportera « aucune notification »"
    )


def test_le_script_sait_compter_les_notifications(db_session, app) -> None:
    """Un membre qui a une notification en a exactement une dans la cloche."""
    page = _bell_page(db_session, app)

    assert len(page.select(f"{BELL} {NOTIFICATION_FORM}")) == 1
    assert len(page.select(NOTIFICATION_BUTTON)) == 1


def test_le_script_sait_lire_l_intitule(db_session, app) -> None:
    """`all_inner_texts()`, côté script, lit ce texte-là.

    Le gabarit échappe l'apostrophe en `&#39;` et le navigateur la
    redonne droite, donc le marqueur du script correspond. Si le libellé
    de `events/notifications.py` change, le script cesse de reconnaître
    un refus — sans cesser de passer.
    """
    page = _bell_page(db_session, app)

    label = page.select_one(NOTIFICATION_BUTTON).get_text(strip=True)
    assert REJECTION_MARKER in label


def test_une_notification_porte_bien_son_url_cible(db_session, app) -> None:
    """L'URL voyage dans un champ caché : c'est elle que le script suit.

    Sans ce champ, `mark_read` retomberait sur le `Referer` puis sur
    « / », et le script verrait un repli silencieux là où il n'y a en
    fait plus de cible du tout.
    """
    page = _bell_page(db_session, app)

    hidden = page.select_one(f'{BELL} {NOTIFICATION_FORM} input[name="url"]')
    assert hidden is not None, "le champ caché `url` a disparu"
    assert hidden["value"] == TARGET_URL
