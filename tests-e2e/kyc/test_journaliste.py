# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import os
import random
from pathlib import Path

from playwright.sync_api import Playwright, sync_playwright

# ROOT_URL = "http://localhost:5000/"
# ROOT_URL = "https://aipress24-kyc.hop.abilian.com/"
ROOT_URL = "http://aipress24-kyc.hop.abilian.com/"

if "ROOT_URL" in os.environ:
    ROOT_URL = os.environ["ROOT_URL"]

random_email = f"sf{random.randint(0, 1000000)}@abilian.com"


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(ROOT_URL)

    page.get_by_role("button", name="Suivant").first.click()

    fill_page_0(page)
    fill_page_1(page)
    fill_page_2(page)
    fill_page_3(page)
    fill_page_4(page)
    fill_page_5_6(page)

    page.locator('input[name="validation1"]').click()

    # ---------------------
    context.close()
    browser.close()


def fill_page_0(page):
    page.get_by_text(
        "Dirigeant.e d’une Agence de presse, d’un journal, d’un magazine, d’un média ou"
    ).click()
    page.get_by_role("button", name="Suivant").first.click()


def fill_page_1(page):
    dummy_file = Path("e2e-tests/cat.jpg")

    page.get_by_text(
        "Dirigeant.e d’une Agence de presse, d’un journal, d’un magazine, d’un média ou"
    ).click()
    page.get_by_role("button", name="Suivant").first.click()

    page.get_by_label("Photo portrait (format JPG,").set_input_files(dummy_file)

    page.get_by_label("Numéro de Carte de presse (*)").click()
    page.get_by_label("Numéro de Carte de presse (*)").fill("123123")

    page.get_by_label("Photo carte de presse (format").set_input_files(dummy_file)

    page.get_by_label("Prénom (*)").click()
    page.get_by_label("Prénom (*)").fill("Stefane")

    page.get_by_label("Nom (*)", exact=True).fill("Fermigier")
    page.get_by_label("Nom (*)", exact=True).press("Tab")

    page.get_by_role("combobox", name="Civilité (*)").fill("M")
    page.get_by_role("option", name="Monsieur").click()

    page.get_by_label("E-mail de connexion (votre E-").click()
    page.get_by_label("E-mail de connexion (votre E-").fill(random_email)

    page.get_by_label("Tel mobile (*)").click()
    page.get_by_label("Tel mobile (*)").fill("123123123")

    page.get_by_label("Mot de passe (*)").click()
    page.get_by_label("Mot de passe (*)").fill("123123asdasd")

    page.get_by_role("button", name="Suivant").first.click()


def fill_page_2(page):
    page.get_by_role("combobox", name="Nom de l’agence de presse, du").click()
    page.get_by_role("option", name="Juin Media (Agence de presse)").click()
    page.get_by_role("option", name="Juin Media (Agence de presse)").press("Escape")

    page.get_by_role("combobox", name="Type d’entreprise de presse").click()
    page.get_by_role("option", name="Association de Journalistes").click()
    page.get_by_role("combobox", name="Type d’entreprise de presse").press("Escape")

    page.get_by_role("combobox", name="Types de presse et médias (").click()
    page.get_by_role("option", name="Presse économique et financiè").click()
    page.get_by_role("combobox", name="Types de presse et médias (").press("Escape")

    page.get_by_role("combobox", name="Fonction du journalisme (").click()
    page.get_by_role("option", name="Chef.fe de projet web").click()
    page.get_by_role("combobox", name="Fonction du journalisme (").press("Escape")

    page.get_by_role("combobox", name="Jusqu’à combien de salariés").click()
    page.get_by_role("option", name="50", exact=True).click()
    page.get_by_role("combobox", name="Jusqu’à combien de salariés").press("Escape")

    page.get_by_role("combobox", name="Pays (*)").click()
    page.get_by_role("option", name="Afrique du Sud").click()

    page.locator("#F028_detail-ts-control").click()
    page.get_by_role("option", name="0002 Pretoria").click()

    page.get_by_role("button", name="Suivant").nth(1).click()


def fill_page_3(page):
    page.get_by_role("combobox", name="Secteurs d’activité couverts").click()
    page.get_by_role("option", name="AGRICULTURE").click()

    page.get_by_role("combobox", name="Secteurs d’activité couverts").press("Escape")
    page.locator("#F034_detail-ts-control").click()
    page.get_by_role("option", name="AGRICULTURE / Agriculture de conservation").click()
    page.locator("#F034_detail-ts-control").press("Escape")

    page.get_by_role("combobox", name="Centres d’intérêt Politiques").click()
    page.get_by_role("option", name="Parlement").click()
    page.get_by_role("combobox", name="Centres d’intérêt Politiques").press("Escape")

    page.get_by_role("combobox", name="Compétences en Journalisme (").click()
    page.get_by_role("option", name="Rédiger des articles").click()
    page.get_by_role("combobox", name="Compétences en Journalisme (").press("Escape")

    page.get_by_role("combobox", name="Langues (plusieurs choix").click()
    page.get_by_role("option", name="Allemand").click()
    page.get_by_role("combobox", name="Langues (plusieurs choix").press("Escape")

    page.get_by_label("Formations (maximum 1500").click()
    page.get_by_label("Formations (maximum 1500").fill("123")
    page.get_by_label("Expériences (maximum 1500").click()
    page.get_by_label("Expériences (maximum 1500").fill("123")
    page.get_by_role("button", name="Suivant").nth(1).click()


def fill_page_4(page):
    page.get_by_label("Hobbies (maximum 1500 caractè").click()
    page.get_by_label("Hobbies (maximum 1500 caractè").fill("123")
    page.get_by_text("J’accepte de prendre un verre").click()
    page.get_by_role("button", name="Suivant").click()


def fill_page_5_6(page):
    page.get_by_text("Faites briller votre média au").click()
    page.get_by_role("button", name="Suivant").click()

    page.get_by_text("Acceptation des Conditions Gé").click()
    page.get_by_role("button", name="Suivant").click()


with sync_playwright() as playwright:
    run(playwright)
