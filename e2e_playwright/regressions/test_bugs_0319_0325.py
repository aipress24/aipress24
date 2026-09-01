# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Régressions — tickets #0319 → #0325, tous revenus « non résolu ».

Une remarque vaut pour la moitié de ce fichier : le client a testé le
build `2026.8.31.1`, et le commit `1b3fd75a9` (« fixes #0325,
#0321/#0322/#0323, #0324 ») **n'y est pas**. Ces tests disent donc deux
choses à la fois — ce qui est réellement cassé dans `HEAD`, et ce qui
ne l'était que faute de déploiement. Les deux se lisent au même
endroit : un test vert ici et un ticket rouge chez le client, c'est un
déploiement en retard, pas un correctif manquant.

Couverture :

- **#0319** — l'organisateur ne doit pas se voir proposer de demander
  une accréditation à son propre événement, et un membre refusé doit
  savoir qu'il l'est.
- **#0320** — les taxonomies des filtres de ciblage doivent être
  chargées, Pays compris.
- **#0321** — les filtres sont regroupés en blocs numérotés, précédés
  de la phrase d'explication.
- **#0322** — le filtre « Toutes fonctions » a disparu.
- **#0323** — le filtre « Transformations majeures » existe et porte
  sa taxonomie.
- **#0324** — le Wall de NEWS ne contient que des actualités : les
  événements en sont sortis (arbitrage du 2026-09-01), et aucune
  carte n'y est vide.
- **#0325** — un membre est présenté par sa fonction, pas par la
  dénomination passe-partout du KYC.
"""

from __future__ import annotations

import json
import re
import time
from typing import TYPE_CHECKING

import pytest
from _shared import _PRESS_MEDIA

if TYPE_CHECKING:
    from playwright.sync_api import Page

_EVENT_DETAIL_RE = re.compile(r"/events/(\d+)$")


# ─── Aides ─────────────────────────────────────────────────────────


def _first_avis_id(page: Page, base_url: str) -> str | None:
    """Id du premier avis d'enquête que possède le membre connecté."""
    page.goto(f"{base_url}/wip/avis-enquete/", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        m = re.search(r"/wip/avis-enquete/(\d+)", href or "")
        if m:
            return m.group(1)
    return None


def _open_ciblage(page: Page, base_url: str) -> None:
    """Ouvrir l'écran de ciblage, ou sauter faute d'avis."""
    avis_id = _first_avis_id(page, base_url)
    if avis_id is None:
        pytest.skip("aucun avis d'enquête pour ce compte")
    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage", wait_until="networkidle"
    )


def _filter_labels(page: Page) -> list[str]:
    return [
        label.strip()
        for label in page.eval_on_selector_all(
            "form#search-form label", "els => els.map(e => e.innerText)"
        )
        if label.strip()
    ]


def _cascade_options(page: Page, parent_name: str) -> int:
    """Nombre de feuilles offertes par une cascade, lues à la source.

    Tom-Select vide le `<select>` d'origine et gère ses propres
    listes : compter `select.options` ne dit rien. Les valeurs sont
    dans `data-options` du conteneur, telles que le serveur les a
    posées.
    """
    raw = page.eval_on_selector_all(
        ".dual-select-cascade",
        """els => els.map(e => ({
            parent: (e.querySelector('select[data-role="parent"]') || {}).name || '',
            options: e.getAttribute('data-options') || '',
        }))""",
    )
    for entry in raw:
        if entry["parent"] != parent_name:
            continue
        parsed = json.loads(entry["options"] or "null")
        if isinstance(parsed, dict):
            return sum(len(v) for v in parsed.values() if isinstance(v, list))
        return len(parsed or [])
    return 0


# ─── #0320 — les taxonomies des filtres de ciblage ─────────────────


def test_bug_0320_cascade_taxonomies_are_loaded(
    page: Page, base_url: str, profile, login
) -> None:
    """Chaque cascade doit proposer sa taxonomie, pas une poignée de
    valeurs.

    « Le filtre secteurs détaillés n'affiche pas la taxonomie dans son
    ensemble. Il n'y a qu'un secteur. » Le seuil est bas exprès : il
    distingue « chargée » de « vide », sans se river au compte du jour.
    """
    login(profile(_PRESS_MEDIA))
    _open_ciblage(page, base_url)

    maigres = {
        parent: _cascade_options(page, parent)
        for parent in (
            "secteur_parent",
            "type_organisation_parent",
            "fonction_pol_adm_parent",
            "fonction_org_priv_parent",
            "fonction_ass_syn_parent",
            "metier_parent",
            "competences_parent",
        )
    }
    vides = {name: n for name, n in maigres.items() if n < 2}
    assert not vides, f"cascades sans taxonomie : {vides} (toutes : {maigres})"


def test_bug_0320_pays_filter_only_offers_countries_that_return_someone(
    page: Page, base_url: str, profile, login
) -> None:
    """« Filtre "Pays" : taxonomie pas chargée. » — **fonctionne comme
    prévu**, décision du 2026-09-01.

    La liste est courte parce que `_make_options` écarte toute valeur
    que ne porte aucun expert du vivier : « sélectionner un critère qui
    produit immédiatement un résultat vide est frustrant ». Charger les
    81 pays de `get_full_countries()` ne changerait donc rien à
    l'écran — les 79 pays sans profil resteraient écartés.

    Ce test épingle la règle plutôt que le nombre : chaque pays proposé
    doit ramener au moins un membre. Il échouerait aussi bien si la
    liste se vidait que si elle se remplissait d'options mortes.

    (Les cascades, elles, affichent la taxonomie entière : elles
    passent par `data-options` et non par `_make_options`. C'est cette
    différence que le client a prise pour une taxonomie manquante.)
    """
    login(profile(_PRESS_MEDIA))
    _open_ciblage(page, base_url)

    labels = page.eval_on_selector_all(
        'form#search-form select[name="pays"] option',
        "els => els.filter(o => o.value).map(o => o.textContent.trim())",
    )
    assert labels, "le filtre Pays ne propose plus aucun pays"
    morts = [label for label in labels if re.search(r"\(\s*0\s*\)$", label)]
    assert not morts, (
        f"des pays sans aucun membre sont proposés : {morts} — la règle "
        f"« pas d'option qui ne ramène rien » a sauté"
    )


# ─── #0321 — hiérarchiser les filtres ──────────────────────────────


def test_bug_0321_filters_are_grouped_in_numbered_blocks(
    page: Page, base_url: str, profile, login
) -> None:
    """« Faire des blocs visuels numérotés, sans modifier les champs. »

    Le compte exact des blocs n'est pas figé : le client en demandait
    sept, dont deux partageaient leurs filtres et ont été réunis. Ce
    qui compte est qu'il y ait des blocs, numérotés, et que le
    journalisme soit traité à part — c'est la confusion signalée.
    """
    login(profile(_PRESS_MEDIA))
    _open_ciblage(page, base_url)

    titles = [
        t.strip()
        for t in page.eval_on_selector_all(
            "form#search-form section h3", "els => els.map(e => e.innerText)"
        )
        if t.strip()
    ]
    assert len(titles) >= 5, f"pas de blocs thématiques : {titles}"
    assert all(re.match(r"^\d+\s*—", t) for t in titles), (
        f"blocs non numérotés : {titles}"
    )
    assert any("journalisme" in t.lower() for t in titles), (
        f"le bloc « presse & médias » manque : {titles}"
    )


def test_bug_0321_intro_sentence_is_present(
    page: Page, base_url: str, profile, login
) -> None:
    """La phrase d'explication demandée mot pour mot par le client."""
    login(profile(_PRESS_MEDIA))
    _open_ciblage(page, base_url)

    body = page.inner_text("body")
    assert "utilisez un ou plusieurs filtres" in body, (
        "la phrase d'introduction du ciblage a disparu"
    )


# ─── #0322 — retirer « Toutes les fonctions » ──────────────────────


def test_bug_0322_toutes_les_fonctions_filter_is_gone(
    page: Page, base_url: str, profile, login
) -> None:
    """« Le filtre "Toutes fonctions" ne correspond à aucune taxonomie.
    Je crains qu'il ne fasse doublon. Autant le retirer. »"""
    login(profile(_PRESS_MEDIA))
    _open_ciblage(page, base_url)

    fautifs = [
        label
        for label in _filter_labels(page)
        if "toutes" in label.lower() and "fonction" in label.lower()
    ]
    assert not fautifs, f"le filtre « Toutes les fonctions » est encore là : {fautifs}"


# ─── #0323 — ajouter « Transformations majeures » ──────────────────


def test_bug_0323_transformations_majeures_filter_exists(
    page: Page, base_url: str, profile, login
) -> None:
    """Le filtre doit exister **et** porter sa taxonomie.

    Un filtre présent mais vide ne vaut pas mieux qu'un filtre absent ;
    c'est la moitié de ce que reprochait #0320 aux autres.
    """
    login(profile(_PRESS_MEDIA))
    _open_ciblage(page, base_url)

    labels = _filter_labels(page)
    assert any("transformation" in label.lower() for label in labels), (
        f"le filtre « Transformations majeures » manque : {labels}"
    )
    count = _cascade_options(page, "transformation_majeure_parent")
    assert count >= 2, f"le filtre existe mais sa taxonomie est vide ({count})"


# ─── #0324 — NEWS ne contient que des actualités ──────────────────


def test_bug_0324_news_wall_holds_news_only(
    page: Page, base_url: str, profile, login
) -> None:
    """« À la place des cartes d'articles, je vois une colonne gauche
    blanche et une colonne droite avec des annonces d'événements. »

    Le ticket avait deux causes, et l'arbitrage du 2026-09-01 les
    supprime toutes les deux d'un coup : les événements quittent le
    fil. Ils y étaient entrés avec le lot `C8`, sur la lecture d'une
    carte de 2022 — « Événements » figure parmi les blocs de la home
    page — et ils y faisaient deux dégâts :

    1. **ils évinçaient les articles.** La fusion gardait les trente
       contenus les plus récents de l'union ; quand les événements
       étaient les plus récents, ils prenaient les trente places ;
    2. **leur carte se dédoublait.** Le gabarit enveloppait le
       composant dans un `<li>`, alors que le composant ouvre le sien.
       Un `<li>` en ferme implicitement un autre : le navigateur
       rendait deux cellules de grille, une vide au liseré rose et une
       avec le contenu. C'est la « colonne gauche blanche ».

    Les trois assertions restent utiles séparément : le fil doit être
    peuplé, ne contenir que des actualités, et aucune carte vide.
    """
    login(profile(_PRESS_MEDIA))
    page.goto(f"{base_url}/wire/tab/wall", wait_until="domcontentloaded")

    cards = page.eval_on_selector_all(
        "#search-results ul > *",
        """els => els.map(e => ({
            cls: e.getAttribute('class') || '',
            len: (e.innerText || '').trim().length,
        }))""",
    )
    assert cards, "le Wall de NEWS est vide"

    evenements = [c for c in cards if "border-pink-500" in c["cls"]]
    assert not evenements, (
        f"{len(evenements)} carte(s) d'événement dans le fil NEWS — les "
        f"événements appartiennent à EVENTS"
    )
    vides = [c for c in cards if c["len"] == 0]
    assert not vides, (
        f"{len(vides)} carte(s) vide(s) sur {len(cards)} — c'est la colonne "
        "blanche signalée par le client"
    )


# ─── #0325 — présenter les membres par leur fonction ───────────────

#: La dénomination passe-partout du KYC, celle que le client ne veut
#: plus voir : « Dirigeant.e d'une Entreprise de Services et Conseils
#: en Transformation des Organisations ».
_KYC_BOILERPLATE = re.compile(
    r"Dirigeant\.e d.une Entreprise de Services|"
    r"Journaliste avec carte de presse travaillant pour",
    re.IGNORECASE,
)


def test_bug_0325_members_are_shown_by_their_function(
    page: Page, base_url: str, profile, login
) -> None:
    """« Je suis présentée par une expression passe-partout et assez
    incommode. Suggestion : Prénom, Nom, Fonction. »"""
    login(profile(_PRESS_MEDIA))
    page.goto(f"{base_url}/swork/members/", wait_until="domcontentloaded")

    body = page.inner_text("body")
    found = _KYC_BOILERPLATE.findall(body)
    assert not found, (
        f"l'annuaire présente encore les membres par la dénomination de "
        f"base du KYC ({len(found)} occurrence(s)) au lieu de leur fonction"
    )


# ─── #0319 — accréditation : l'organisateur et le refusé ───────────


def _publish_own_event(page: Page, base_url: str, authed_get, payload_of) -> dict:
    """Créer puis publier un événement au nom du membre connecté.

    Rend `{"wip_id", "public_id", "title"}`. Les deux identifiants
    diffèrent : le miroir public est une autre ligne, reliée par
    `EventPost.eventroom_id`.
    """
    page.goto(f"{base_url}/wip/events/new", wait_until="domcontentloaded")
    title = f"e2e-0319-{int(time.time() * 1000) % 10**10}"
    start = time.strftime("%Y-%m-%dT%H:%M", time.localtime(time.time() + 86400 * 30))
    end = time.strftime(
        "%Y-%m-%dT%H:%M", time.localtime(time.time() + 86400 * 30 + 3600)
    )
    payload = payload_of(
        titre=title,
        start_time=start,
        end_time=end,
        # MOD-01 : sans adresse, `check_publishable` refuse un événement
        # en présentiel — et le mode par défaut l'est.
        address="13 rue du cours du Pétrole, Le Havre",
    )

    create = page.evaluate(
        """async (args) => {
            const r = await fetch(args.url, {
                method: 'POST', credentials: 'same-origin',
                body: new URLSearchParams(args.data),
                headers: {'Content-Type': 'application/x-www-form-urlencoded'},
            });
            return {status: r.status, url: r.url, redirected: r.redirected};
        }""",
        {"url": f"{base_url}/wip/events/", "data": payload},
    )
    assert create["redirected"], f"création refusée : {create}"

    wip_id = _find_wip_event_id(page, base_url, title)
    assert wip_id, f"événement {title!r} absent de /wip/events/"
    published = authed_get(f"{base_url}/wip/events/publish/{wip_id}/")
    assert published["status"] < 400, f"publication : {published}"

    public_id = _find_public_event_id(page, base_url, title)
    return {"wip_id": wip_id, "public_id": public_id, "title": title}


def _find_wip_event_id(page: Page, base_url: str, title: str) -> str | None:
    page.goto(f"{base_url}/wip/events/", wait_until="domcontentloaded")
    return page.evaluate(
        """(needle) => {
            for (const row of document.querySelectorAll('tr')) {
                if (!(row.textContent || '').includes(needle)) continue;
                for (const a of row.querySelectorAll('a[href]')) {
                    const m = (a.getAttribute('href') || '')
                        .match(/\\/wip\\/events\\/(\\d+)(?:\\/|$)/);
                    if (m) return m[1];
                }
            }
            return null;
        }""",
        title,
    )


def _find_public_event_id(page: Page, base_url: str, title: str) -> str | None:
    page.goto(f"{base_url}/events/", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        """els => els.map(e => ({
            href: e.getAttribute('href') || '',
            text: (e.closest('li') || e).innerText || '',
        }))"""
    )
    for entry in hrefs or ():
        if title not in entry["text"]:
            continue
        path = entry["href"].split("?", 1)[0].rstrip("/")
        m = _EVENT_DETAIL_RE.search(path)
        if m:
            return m.group(1)
    return None


@pytest.mark.mutates_db
def test_bug_0319_organiser_is_not_offered_accreditation_on_own_event(
    page: Page,
    base_url: str,
    profile,
    login,
    authed_get,
    authed_post,
    event_create_payload,
) -> None:
    """« L'organisateur tombe sur la demande d'accréditation comme s'il
    voulait s'accréditer lui-même à l'événement qu'il publie. »

    La règle est déjà écrite dans `sees_full_content` : l'exception
    accordée à l'organisateur porte « sur la visibilité seulement »
    et « n'ouvre pas le droit de demander une accréditation ». Le
    gabarit, lui, s'appuie sur `sees_content` — donc la propose.

    Deux assertions, parce que masquer sans refuser laisse passer un
    POST forgé : c'est l'argument que `is_open` porte déjà en
    commentaire.
    """
    login(profile(_PRESS_MEDIA))
    event = _publish_own_event(page, base_url, authed_get, event_create_payload)
    public_id = event["public_id"]
    try:
        assert public_id, f"{event['title']!r} publié mais absent de /events/"
        page.goto(f"{base_url}/events/{public_id}", wait_until="domcontentloaded")
        block = page.locator(f"#accreditation-block-{public_id}")
        text = block.inner_text() if block.count() else ""
        for interdit in (
            "Demande d'accréditation",
            "Annuler ma demande",
            "Se désinscrire",
        ):
            assert interdit not in text, (
                f"l'organisateur se voit proposer « {interdit} » sur son "
                f"propre événement (bloc : {text!r})"
            )

        refus = authed_post(
            f"{base_url}/events/{public_id}",
            {"action": "request-accreditation"},
        )
        assert refus["status"] == 403, (
            f"l'organisateur peut s'accréditer lui-même par un POST direct : {refus}"
        )
    finally:
        authed_get(f"{base_url}/wip/events/unpublish/{event['wip_id']}/")
        authed_get(f"{base_url}/wip/events/{event['wip_id']}/delete")


@pytest.mark.mutates_db
@pytest.mark.parallel_unsafe
def test_bug_0319_rejected_member_is_told_so(
    page: Page,
    base_url: str,
    profiles,
    profile,
    login,
    authed_get,
    authed_post,
    event_create_payload,
) -> None:
    """« Le solliciteur ne reçoit pas un message clair de refus. »

    Parcours complet : l'organisateur publie, un second journaliste
    demande, l'organisateur refuse, le second revient sur la page.
    """
    organiser = profile(_PRESS_MEDIA)
    candidats = [
        p
        for p in profiles
        if p["community"] == _PRESS_MEDIA and p["email"] != organiser["email"]
    ]
    if not candidats:
        pytest.skip("un seul profil PRESS_MEDIA — pas de second demandeur")
    demandeur = candidats[0]

    login(organiser)
    event = _publish_own_event(page, base_url, authed_get, event_create_payload)
    public_id, wip_id = event["public_id"], event["wip_id"]
    try:
        assert public_id, f"{event['title']!r} publié mais absent de /events/"

        # Le demandeur sollicite.
        login(demandeur)
        demande = authed_post(
            f"{base_url}/events/{public_id}", {"action": "request-accreditation"}
        )
        assert demande["status"] == 200, f"demande refusée : {demande}"

        # L'organisateur refuse.
        login(organiser)
        page.goto(
            f"{base_url}/wip/events/{wip_id}/accreditations",
            wait_until="domcontentloaded",
        )
        user_ids = page.eval_on_selector_all(
            'input[name="user_ids"]', "els => els.map(e => e.value)"
        )
        assert user_ids, "la demande n'apparaît pas dans l'écran d'accréditation"
        rejet = authed_post(
            f"{base_url}/wip/events/{wip_id}/accreditations",
            {"_action": "reject", "user_ids": user_ids[0]},
        )
        assert rejet["status"] < 400, f"refus : {rejet}"

        # Le demandeur doit le savoir.
        login(demandeur)
        page.goto(f"{base_url}/events/{public_id}", wait_until="domcontentloaded")
        block = page.locator(f"#accreditation-block-{public_id}")
        text = (block.inner_text() if block.count() else "").strip()
        assert "refus" in text.lower(), (
            f"le membre refusé ne lit aucun message de refus sur la page de "
            f"l'événement (bloc : {text!r})"
        )
    finally:
        login(organiser)
        authed_get(f"{base_url}/wip/events/unpublish/{wip_id}/")
        authed_get(f"{base_url}/wip/events/{wip_id}/delete")
