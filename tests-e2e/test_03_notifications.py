# Copyright (c) 2021-2026 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""La cloche mène-t-elle quelque part ? — ticket #0319.

Erick, 2026-09-02 : « L'alerte à la cloche du refus d'accréditation
conduit à un bug (les deux messages en haut). Lorsque je clique sur
chacun des deux messages en haut de liste on tombe sur ceci », suivi
d'une capture de page d'erreur.

Le symptôme n'est pas propre à l'accréditation. Une notification porte
une URL calculée au moment où elle est posée, et personne ne revérifie
ensuite qu'elle mène encore à une page — l'objet peut avoir été
dépublié, supprimé, ou n'avoir jamais été visible pour ce destinataire.
Le parcours est le même pour les onze producteurs de notifications de la
plateforme.

Ce module reproduit donc la **classe** de bug plutôt que le seul cas
d'Erick : pour chaque rôle, ouvrir la cloche, cliquer chaque
notification, et vérifier que la page d'arrivée existe.

Ce qui est vérifié à chaque clic, et pourquoi :

- **Le statut HTTP de la navigation.** C'est la page d'erreur de la
  capture d'Erick. Un 404 ou un 500 est ici la reproduction du bug.
- **L'URL finale.** `notifications.mark_read` fait passer la cible par
  `_is_safe_url` et retombe silencieusement sur « / » si elle échoue :
  la notification « ne fait rien » au lieu de tomber en erreur, ce qui
  se diagnostique encore plus mal. `notes/lessons-learned.md` en fait
  une règle — « always assert the final URL ».

Lancement, contre un serveur de développement — la backdoor exige
`UNSECURE=True`, donc jamais la production :

    pytest tests-e2e/test_03_notifications.py --browser firefox --base-url http://127.0.0.1:5000

Ajouter `--headed --video on` pour voir le parcours.

Pas de coupure des sockets HMR ici, contrairement à ce que prescrit
`notes/lessons-learned.md` (« route.abort() sur `**://localhost:3000/**`
dans une fixture autouse »). Cette recette **casse l'application** en
mode développement : le même serveur Vite sert `@vite/client` et
`main.js`, et `main.js` est un module ES qui dépend du client. Coupé,
`window.Alpine` reste `undefined`, aucun menu déroulant ne s'ouvre, et
le parcours échoue sur une attente de visibilité — vérifié dans les deux
sens. Si le blocage HMR de Firefox se manifeste un jour ici, c'est la
websocket qu'il faudra viser (`page.route_web_socket`), pas l'origine.

Le module est autonome à dessein : `tests-e2e/` ne se collecte plus
(ses imports relatifs supposent un paquet nommé `tests-e2e`, ce qu'un
tiret interdit), et son tier `tepyd` est commenté dans `pyproject.toml`.
Ce script ne dépend que de son `conftest.py` voisin, que pytest charge
par chemin.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

#: Le mur d'actualités : la page privée la plus légère qui porte
#: l'en-tête, donc la cloche.
NEWS_PATH = "/wire/tab/wall"

#: Les rôles que la backdoor sait endosser, et le nom qu'elle attend.
ROLES = {
    "journaliste": "journalist",
    "communicant": "press_relations",
    "expert": "expert",
    "transformer": "transformer",
    "etudiant": "academic",
}

#: Le conteneur du menu déroulant qui porte les formulaires de la
#: cloche. La macro `simple_dropdown` donne le même intitulé masqué
#: (« Open user menu ») au bouton de la cloche et à celui du profil —
#: on désigne donc la cloche par ce qu'elle contient, pas par son nom.
BELL = 'div.indicator:has(form[action*="/notifications/"])'
BELL_BUTTON = f'{BELL} button[x-ref="button"]'
NOTIFICATION_FORM = 'form[action*="/notifications/"][action$="/read"]'

#: Ce que la plateforme envoie quand une demande d'accréditation est
#: refusée (`events/notifications.py`, NOT-03). Sert à isoler le cas
#: précis du ticket parmi les notifications présentes.
REJECTION_MARKER = "n'a pas été retenue"

#: Toute page d'AIpress24 s'intitule « … - AiPRESS24 ».
AIPRESS24_TITLE = re.compile(r".* - AiPRESS24")


def _login_as(page: Page, role: str, base_url: str) -> None:
    """Endosser un rôle via la backdoor de développement.

    Elle prend le **premier** utilisateur portant le rôle, ce qui suffit
    ici : on ne cherche pas un membre en particulier, on parcourt les
    notifications de chacun.
    """
    page.goto(f"{base_url}/backdoor/")
    page.goto(f"{base_url}/backdoor/{ROLES[role]}")
    page.wait_for_load_state()


@pytest.fixture(autouse=True)
def _target_is_usable(page: Page, base_url: str):
    """Refuser de tourner contre une cible qui ne peut rien prouver.

    Deux échecs distincts, tous deux rencontrés en essayant ce script :

    - **Ce n'est pas AIpress24.** Un `--base-url` pointant ailleurs rend
      des 404 d'une autre application : la cloche n'existe pas, le
      parcours ne trouve rien, et la suite se termine sur « passed »
      sans avoir cliqué quoi que ce soit. Le port 5000 de la machine
      servait Abilian SBE au premier essai.
    - **La backdoor est fermée.** Sans `UNSECURE=True` elle rend 403, et
      aucun rôle ne peut être endossé.

    On sonde `/backdoor/` plutôt que `/` : c'est la page dont le script
    dépend, et elle porte un titre — `/` redirige vers `/auth/login`,
    qui n'a pas de `<title>` du tout, ce qu'un contrôle sur la racine
    lisait comme « ce n'est pas AIpress24 ».
    """
    response = page.goto(f"{base_url}/backdoor/")
    status = response.status if response else 0
    title = page.title()

    if status == 403:
        pytest.fail(
            f"{base_url} est bien AIpress24, mais la backdoor est fermée "
            f"(403). Lancer le serveur avec UNSECURE=True."
        )
    if not AIPRESS24_TITLE.match(title):
        pytest.fail(
            f"{base_url} ne sert pas AIpress24 (statut {status}, titre "
            f"« {title} »). Démarrer le serveur — `make run` — et pointer "
            f"--base-url dessus."
        )


def _open_bell(page: Page) -> int:
    """Ouvrir la cloche, et rendre le nombre de notifications listées.

    Le panneau est un `x-show` d'Alpine : ses formulaires sont dans le
    DOM avant l'ouverture, mais invisibles, donc non cliquables. On
    l'ouvre vraiment, comme le ferait l'utilisateur.
    """
    bell = page.locator(BELL_BUTTON)
    if bell.count() == 0:
        # Aucun formulaire de notification dans la page : la cloche est
        # vide (« Pas de nouvelle notification »).
        return 0
    bell.first.click()
    forms = page.locator(f"{BELL} {NOTIFICATION_FORM}")
    expect(forms.first).to_be_visible()
    return forms.count()


def _notification_labels(page: Page) -> list[str]:
    """Les intitulés visibles, dans l'ordre où la cloche les liste."""
    return [
        (text or "").strip()
        for text in page.locator(f"{BELL} {NOTIFICATION_FORM} button").all_inner_texts()
    ]


def _click_notification(page: Page, index: int, base_url: str) -> tuple[int, str]:
    """Cliquer la n-ième notification et rendre (statut, URL finale).

    Le clic poste vers `mark_read`, qui redirige vers la cible. On
    retient le statut de la **dernière** réponse de type document :
    c'est la page sur laquelle l'utilisateur atterrit, celle de la
    capture d'écran d'Erick.
    """
    statuses: list[int] = []

    def _record(response) -> None:
        if response.request.resource_type == "document":
            statuses.append(response.status)

    page.goto(base_url + NEWS_PATH)
    _open_bell(page)

    page.on("response", _record)
    try:
        page.locator(f"{BELL} {NOTIFICATION_FORM} button").nth(index).click()
        page.wait_for_load_state()
    finally:
        page.remove_listener("response", _record)

    return (statuses[-1] if statuses else 0), page.url


def _walk_notifications(page: Page, base_url: str, role: str) -> tuple[int, list[str]]:
    """Cliquer chaque notification d'un rôle.

    Rend le nombre de notifications parcourues **et** la liste des
    échecs. Le compte est ce qui distingue « tout va bien » de « il n'y
    avait rien à regarder ».
    """
    _login_as(page, role, base_url)
    page.goto(base_url + NEWS_PATH)

    count = _open_bell(page)
    if count == 0:
        return 0, []
    labels = _notification_labels(page)

    failures: list[str] = []
    for index in range(count):
        status, final_url = _click_notification(page, index, base_url)
        label = labels[index] if index < len(labels) else f"#{index}"
        summary = " ".join(label.split())[:70]

        if status >= 400:
            failures.append(f"[{role}] HTTP {status} sur « {summary} » → {final_url}")
        elif final_url.rstrip("/") == base_url.rstrip("/"):
            # `_is_safe_url` a refusé la cible : la notification ne mène
            # nulle part, silencieusement.
            failures.append(
                f"[{role}] repli sur l'accueil pour « {summary} » — "
                f"cible rejetée par le contrôle same-origin"
            )
    return count, failures


@pytest.mark.parametrize("role", sorted(ROLES))
def test_toute_notification_mene_a_une_page_valide(
    page: Page, base_url: str, role: str
) -> None:
    """La classe de bug : une cloche qui mène à une page d'erreur.

    Le test ne présume pas du contenu de la base : s'il n'y a aucune
    notification pour ce rôle, il n'y a rien à reprocher. Ce qui est
    interdit, c'est qu'une notification *présente* n'aboutisse pas.
    """
    walked, failures = _walk_notifications(page, base_url, role)
    if walked == 0:
        pytest.skip(
            f"aucune notification pour le rôle « {role} » — rien à vérifier. "
            f"Un « passed » ici ne dirait rien du bug #0319."
        )
    assert not failures, "\n".join(failures)


def test_la_cloche_d_un_refus_d_accreditation_mene_a_l_evenement(
    page: Page, base_url: str
) -> None:
    """Le cas exact du ticket #0319, isolé.

    Le test au-dessus couvre déjà ce chemin quand la base porte un
    refus. Celui-ci le nomme, pour que l'échec dise « accréditation »
    plutôt que « une notification parmi d'autres » — et il est ignoré
    plutôt que vert quand la donnée n'est pas là, faute de quoi il
    passerait sans rien avoir vérifié.
    """
    seen = False
    failures: list[str] = []

    for role in ROLES:
        _login_as(page, role, base_url)
        page.goto(base_url + NEWS_PATH)
        if _open_bell(page) == 0:
            continue

        labels = _notification_labels(page)
        for index, label in enumerate(labels):
            if REJECTION_MARKER not in label:
                continue
            seen = True
            status, final_url = _click_notification(page, index, base_url)
            if status >= 400 or final_url.rstrip("/") == base_url.rstrip("/"):
                failures.append(
                    f"[{role}] refus d'accréditation : HTTP {status} → {final_url}"
                )

    if not seen:
        pytest.skip(
            "aucun refus d'accréditation dans la base de test — "
            "refuser une demande depuis WORK/Event'Room pour l'alimenter"
        )
    assert not failures, "\n".join(failures)
