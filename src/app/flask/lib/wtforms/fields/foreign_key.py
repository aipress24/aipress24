"""Champ de sélection d'une clé étrangère facultative."""
# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import fields


class OptionalIdField(fields.SelectField):
    """Un `SelectField` d'identifiants, qui rend un entier ou `None`.

    Un `SelectField` rend toujours des chaînes : l'option vide devient
    `""` et un choix devient `"42"`. Écrire l'un ou l'autre dans une
    colonne d'entiers échoue sur PostgreSQL, et passe silencieusement
    sur SQLite — le pire des deux mondes.

    La conversion vit ici plutôt que dans la vue parce que c'est une
    propriété du champ : un sélecteur d'identifiants rend un
    identifiant. Le socle traite déjà `media_id` de l'autre façon, par
    un `int()` dans le gestionnaire de POST ; on ne le touche pas, mais
    on ne recopie pas non plus.

    `""` devient `None` et non `0` : l'absence de choix est une absence,
    pas la ligne d'identifiant zéro.
    """

    def populate_obj(self, obj: object, name: str) -> None:
        raw = (self.data or "").strip() if isinstance(self.data, str) else self.data
        setattr(obj, name, int(raw) if raw else None)

    def process_data(self, value: object) -> None:
        """Rendre un identifiant venu du modèle : `None` → option vide."""
        super().process_data("" if value is None else str(value))
