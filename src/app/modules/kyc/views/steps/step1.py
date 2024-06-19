# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from textwrap import dedent

from flask import request
from markupsafe import Markup

from .base import Step

# language=jinja2
T1 = """
<div class="content">
    <h2 class="mt-8 mb-4">A quelle communauté professionnelle appartenez-vous ?</h2>

    <p>
    Je suis <b>Journaliste professionnel.le</b>:
    </p>

    <fieldset>
        <div>
          <input type="radio" id="j1" name="profile" value="j1">
          <label for="j1">Avec carte de presse</label>
        </div>

        <div>
          <input type="radio" id="j2" name="profile" value="j2">
          <label for="j2">Sans carte de presse mais travaillant pour des médias reconnus (CPPAP, Arcom)</label>
        </div>

        <div>
          <input type="radio" id="j3" name="profile" value="j3">
          <label for="j3">Je suis journaliste d’entreprise</label>
        </div>
    </fieldset>

    <p>Je suis <b>Communicant.e professionnel.le</b>:</p>

    <fieldset>
        <div>
          <input type="radio" id="c1" name="profile" value="c1">
          <label for="c1">Je suis Communicant.e professionnel.le en agence</label>
        </div>

        <div>
          <input type="radio" id="c2" name="profile" value="c2">
          <label for="c2">Je suis Communicant.e professionnel.le indépendant.e</label>
        </div>

        <div>
          <input type="radio" id="c3" name="profile" value="c3">
          <label for="c3">Je suis Communicant.e professionnel.le chez l’annonceur</label>
        </div>
    </fieldset>

    <p>Je suis <b>Expert.e</b>:</p>

    <fieldset>
        <div>
          <input type="radio" id="x1" name="profile" value="x1">
          <label for="x1">Je suis Expert.e salarié.e dans une organisation</label>
        </div>

        <div>
          <input type="radio" id="x2" name="profile" value="x2">
          <label for="x2">Je suis Expert.e et je suis en charge des relations presse dans mon organisation</label>
        </div>

        <div>
          <input type="radio" id="x3" name="profile" value="x3">
          <label for="x3">Je dirige une startup</label>
        </div>

        <div>
          <input type="radio" id="x4" name="profile" value="x4">
          <label for="x4">Je suis Expert.e indépendant.e</label>
        </div>
    </fieldset>

    <p>Je suis <b>IT Transformer</b>:</p>

    <fieldset>
        <div>
          <input type="radio" id="i1" name="profile" value="i1">
          <label for="i1">Je suis IT Transformer salarié.e d’une organisation</label>
        </div>

        <div>
          <input type="radio" id="i2" name="profile" value="i2">
          <label for="i2">Je suis IT Transformer salarié.e et je suis en charge des relations presse dans mon organisation</label>
        </div>

        <div>
          <input type="radio" id="i3" name="profile" value="i3">
          <label for="i3">Je suis IT Transformer indépendant.e</label>
        </div>
    </fieldset>

    <p>Je suis <b>Etudiant.e</b>:</p>

    <fieldset>
        <div>
          <input type="radio" id="e1" name="profile" value="e1">
          <label for="e1">Je suis Etudiant.e</label>
        </div>
    </fieldset>
</div>
"""


class Form:
    def render(self):
        return Markup(T1)

    class Meta:
        groups = []


class Step1(Step):
    title = "Inscription sur Aipress24 (1/N)"
    is_first = True
    form_class = Form
    preamble_md = dedent(
        """
    Ce questionnaire va vous permettre de déterminer votre communauté d'appartenance dans Aipress24.

    Répondez-y avec soin, vos réponses seront vérifiées avant que votre inscription ne soit validée.
    """
    )

    def get_next_step_id(self) -> str:
        match profile := request.form.get("profile"):
            case None:
                return ""
            case "j1" | "j2" | "j3":
                return f"step2-{profile}"
            case "c1" | "c2" | "c3":
                return f"step2-{profile}"
            case "x1" | "x2" | "x3" | "x4":
                return f"step2-{profile}"
            case "i1" | "i2" | "i3":
                return f"step2-{profile}"
            case "e1":
                return f"step2-{profile}"
            case _:
                raise ValueError(f"Unknown profile: {profile!r}")
