# ruff: noqa: INP001
# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Régressions — tickets #0333, #0343, #0344.

- **#0344** — « quelque soit le secteur d'activité choisi je n'obtiens
  aucun nom. En revanche si j'inclus des journalistes […] j'obtiens des
  profils. » L'exclusion des journalistes passait **après** le
  pré-filtre thématique, dont le repli était calculé sur une population
  que l'exclusion vidait ensuite.
- **#0343** — un chef de rubrique commande un sujet sans connaître la
  date de paiement. Le champ a quitté le formulaire.
- **#0333** — après un changement de taxonomie, rouvrir puis
  ré-enregistrer son KYC sans y toucher refusait les valeurs devenues
  obsolètes. Elles restent acceptées ; seul l'ajout d'une valeur
  retirée est refusé.

**Ce que ce fichier prouve, et ce qu'il ne prouve pas.** Seul #0343
mord ici : vérifié en remisant le correctif, son test échoue et les
autres passent. #0344 demande une population précise — un secteur dont
les candidats sont majoritairement des journalistes — et #0333 un
profil portant une valeur qu'aucune taxonomie n'offre plus ; ni l'une
ni l'autre n'est présente dans la base de test, et aucune ne se
fabrique depuis un navigateur. Ces deux-là gardent donc le parcours,
pas la régression, qui est épinglée là où la population se construit :
`tests/a_unit/modules/wip/services/test_expert_filter_pool_order.py`
et `tests/a_unit/modules/kyc/test_retained_values.py`.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlencode

import pytest
from _shared import _PRESS_MEDIA

if TYPE_CHECKING:
    from playwright.sync_api import Page


def _first_avis_id(page: Page, base_url: str) -> str | None:
    page.goto(f"{base_url}/wip/avis-enquete/", wait_until="domcontentloaded")
    hrefs = page.locator("a[href]").evaluate_all(
        "els => els.map(e => e.getAttribute('href'))"
    )
    for href in hrefs or ():
        m = re.search(r"/wip/avis-enquete/(\d+)", href or "")
        if m:
            return m.group(1)
    return None


def _ciblage(page: Page, base_url: str, avis_id: str, **params: str) -> int:
    """Ouvrir le ciblage avec ces critères et compter les profils offerts.

    Un GET portant les valeurs du formulaire, comme le fait la page
    elle-même à chaque changement de sélecteur (`fireSearchUpdate`).
    """
    query = urlencode({"selector_change": "1", **params})
    page.goto(
        f"{base_url}/wip/avis-enquete/{avis_id}/ciblage?{query}",
        wait_until="networkidle",
    )
    return page.locator('input[name^="expert:"]').count()


# ─── #0344 — le ciblage sans les journalistes ──────────────────────


def test_the_ciblage_offers_profiles_without_journalists(
    page: Page, base_url: str, profile, login
) -> None:
    """Le vivier hors presse doit rester peuplé — garde d'écran.

    La base de test porte les cinq communautés, et les quatre autres
    que la presse y sont majoritaires : un écran vide ne peut donc pas
    s'expliquer par l'absence de candidats. Ne reproduit pas #0344,
    dont le déclencheur est une population que cette base n'a pas.
    """
    login(profile(_PRESS_MEDIA))
    avis_id = _first_avis_id(page, base_url)
    if avis_id is None:
        pytest.skip("aucun avis d'enquête pour ce compte")

    sans_journalistes = _ciblage(page, base_url, avis_id)

    assert sans_journalistes > 0, (
        "aucun profil proposé sans les journalistes — les communautés "
        "experts / transformers / consultants RP ne sont pas chargées (#0344)"
    )


def test_ticking_the_journalists_box_only_adds(
    page: Page, base_url: str, profile, login
) -> None:
    """Inclure les journalistes élargit le vivier, ne le remplace pas."""
    login(profile(_PRESS_MEDIA))
    avis_id = _first_avis_id(page, base_url)
    if avis_id is None:
        pytest.skip("aucun avis d'enquête pour ce compte")

    sans = _ciblage(page, base_url, avis_id)
    avec = _ciblage(page, base_url, avis_id, include_journalists="on")

    assert avec >= sans, f"cocher la case a réduit le vivier : {sans} → {avec}"


# ─── #0343 — la date de paiement ───────────────────────────────────


def test_bug_0343_the_commande_form_no_longer_asks_for_a_payment_date(
    page: Page, base_url: str, profile, login
) -> None:
    """« Peut on supprimer la date de paiement ? » — oui.

    Les trois autres dates sont vérifiées dans la foulée : sans elles,
    l'absence de la quatrième ne prouverait que le fait que la page
    n'a pas rendu son formulaire.
    """
    login(profile(_PRESS_MEDIA))
    page.goto(f"{base_url}/wip/commandes/new", wait_until="domcontentloaded")

    for date_field in (
        "date_limite_validite",
        "date_bouclage",
        "date_parution_prevue",
    ):
        assert page.locator(f'[name="{date_field}"]').count() > 0, (
            f"{date_field} a disparu du formulaire de commande"
        )
    assert page.locator('[name="date_paiement"]').count() == 0, (
        "le formulaire de commande demande encore une date de paiement (#0343)"
    )


# ─── #0333 — les valeurs d'une taxonomie retirée ───────────────────


@pytest.mark.mutates_db
def test_an_untouched_profile_can_be_saved_again(
    page: Page, base_url: str, profile, login
) -> None:
    """Rouvrir son KYC et le ré-enregistrer sans rien changer.

    C'est le geste du ticket. Une valeur que la taxonomie courante
    n'offre plus doit repasser telle quelle : elle est déjà au profil,
    le membre ne l'a pas choisie aujourd'hui, et rien de ce qu'il peut
    faire ici ne la corrige.

    **Garde de parcours, pas régression.** Aucun profil de la base de
    test ne porte de valeur périmée — vérifié en remisant le
    correctif : ce test passe quand même. Il tient le geste ouvert ;
    la règle est épinglée sur des valeurs plantées dans
    `tests/a_unit/modules/kyc/test_retained_values.py`.
    """
    login(profile(_PRESS_MEDIA))
    page.goto(f"{base_url}/kyc/modify", wait_until="domcontentloaded")
    assert "/kyc/" in page.url, f"le parcours de modification n'a pas ouvert: {page.url}"

    response = page.goto(f"{base_url}/kyc/wizard/P002", wait_until="networkidle")
    # Vérifier que la page est vivante AVANT de chercher un message
    # d'erreur : une 500 n'en affiche pas davantage, et ce test est
    # passé au vert contre une 500 exactement pour cette raison.
    assert response is not None, "le wizard n'a pas répondu"
    assert response.status == 200, f"le wizard ne rend pas: {response.status}"
    assert page.locator('[name="civilite"]').count() > 0, (
        "le wizard a répondu 200 sans rendre ses champs"
    )

    # Ce que le serveur a rendu, renvoyé tel quel.
    page.evaluate(
        """() => {
            const form = document.querySelector('form');
            if (form) form.submit();
        }"""
    )
    page.wait_for_load_state("networkidle")

    errors = page.locator("text=/n[’']est pas une valeur|Not a valid choice/i")
    assert errors.count() == 0, (
        "ré-enregistrer un profil intact est refusé sur une valeur "
        "que la taxonomie n'offre plus (#0333)"
    )
