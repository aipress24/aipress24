# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable
from json import dumps, loads
from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import request, session
from werkzeug.exceptions import BadRequest

from app.enums import MODE_LABELS, PRICING_LABELS
from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.kyc.field_label import country_code_to_country_name
from app.services.taxonomies import get_taxonomy

if TYPE_CHECKING:
    from sqlalchemy.orm import InstrumentedAttribute


def enum_label(labels: dict):
    """Fabriquer la fonction de libellé d'un filtre adossé à une
    énumération.

    Appelée avec **deux types** : un membre de l'énumération quand elle
    vient de la requête qui calcule les options, une `str` quand elle
    vient du filtre actif, restauré depuis la session en JSON. Un
    `StrEnum` s'indexe par sa valeur dans les deux cas — c'est ce qui
    permet à une seule table de servir les deux chemins, là où
    `EventMode(value)` ou `value.name` casserait sur l'un des deux.

    Une fabrique et non deux fonctions jumelles : « Format » et
    « Tarif » ne différaient que par leur dictionnaire, et un troisième
    filtre énuméré en aurait fait une troisième copie.
    """
    return lambda value: labels.get(value, str(value))


mode_label = enum_label(MODE_LABELS)
pricing_label = enum_label(PRICING_LABELS)


FILTER_SPECS: list[dict] = [
    {
        "id": "genre",
        "label": "Type d'événement",
        "column": "genre",
        # Order the options like the taxonomy, not alphabetically.
        "taxonomy": "events",
    },
    {
        "id": "sector",
        "label": "Secteur",
        "column": "sector",
    },
    {
        "id": "section",
        "label": "Rubrique",
        "column": "section",
    },
    {
        "id": "topic",
        "label": "Type d'info",
        "column": "topic",
    },
    # Décision `M1` — deux axes **multivalués** : un événement s'adresse à
    # plusieurs fonctions à la fois. `"multi"` change deux choses, et
    # seulement deux : les options se dépouillent des listes rendues par
    # `TagList`, et la clause SQL devient `contains_tag` au lieu d'`in_`.
    {
        "id": "competences",
        "label": "Compétences visées",
        "column": "competences",
        "multi": True,
    },
    {
        "id": "fonctions",
        "label": "Fonctions visées",
        "column": "fonctions",
        "multi": True,
    },
    {
        "id": "mode",
        "label": "Format",
        "column": "mode",
        "label_function": mode_label,
    },
    {
        "id": "pricing",
        "label": "Tarif",
        "column": "pricing",
        "label_function": pricing_label,
    },
    {
        "id": "pays_zip_ville",
        "label": "Pays",
        "column": "pays_zip_ville",
        "label_function": country_code_to_country_name,
    },
    {
        "id": "departement",
        "label": "Département",
        "column": "departement",
    },
    {
        "id": "ville",
        "label": "Ville",
        "column": "ville",
    },
]

SORTER_OPTIONS = [
    ("date", "Date"),
    ("views", "Popularité (vues)"),
    ("likes", "Popularité (likes)"),
    ("shares", "Popularité (partages)"),
]

FILTER_TAG_LABEL = {
    "mode": "format",
    "pricing": "tarif",
    "sector": "secteur",
    "genre": "type",
    "pays_zip_ville": "pays",
    "departement": "dépt",
    "ville": "ville",
}

FILTER_SPECS_BY_ID = {spec["id"]: spec for spec in FILTER_SPECS}


class FilterBar:
    def __init__(self) -> None:
        self.state = self.get_state()
        self.filters = self.get_filters()

    #
    # Accessors
    #
    @property
    def active_filters(self) -> list:
        active = []
        for filter in self.state.get("filters", []):
            spec = FILTER_SPECS_BY_ID.get(filter["id"])
            label = filter["value"]
            if spec and (label_func := spec.get("label_function")):
                label = label_func(label)

            active.append(
                {
                    "type": "selector",
                    "id": filter["id"],
                    "value": filter["value"],
                    "label": label,
                    "tag_label": FILTER_TAG_LABEL.get(filter["id"], ""),
                }
            )
        return active

    @property
    def sorter(self) -> dict:
        return {
            "options": [
                {
                    "value": opt[0],
                    "label": opt[1],
                    "selected": opt[0] == self.state.get("sort-by", "date"),
                }
                for opt in SORTER_OPTIONS
            ],
        }

    @property
    def sort_order(self) -> str:
        return self.state.get("sort-by", "date")

    #
    # State management
    #
    def get_state(self) -> dict:
        state_json = session.get("events:state")
        if state_json is None:
            return {}
        return loads(state_json)

    def save_state(self) -> None:
        session["events:state"] = dumps(self.state)

    def reset(self) -> None:
        self.state = {}
        self.save_state()

    def update_state(self) -> None:
        form = request.form
        action = form.get("action", "")
        form_value = form.get("value", "")
        form_id = form.get("id", "")

        match action:
            case "toggle" if form_id and form_value:
                self.toggle_filter(form_id, form_value)
            case "remove" if form_id and form_value:
                self.remove_filter(form_id, form_value)
            case "sort-by" if form_value:
                self.sort_by(form_value)
            case _:
                raise BadRequest

        self.save_state()

    def toggle_filter(self, id: str, value: str) -> None:
        if self.has_filter(id, value):
            self.remove_filter(id, value)
        else:
            self.add_filter(id, value)

    def has_filter(self, id: str, value: str) -> bool:
        filters = self.state.get("filters", [])
        return any(
            filter["id"] == id and filter["value"] == value for filter in filters
        )

    def remove_filter(self, id: str, value: str) -> None:
        filters = self.state.get("filters", [])
        for i, filter in enumerate(filters):
            if filter["id"] == id and filter["value"] == value:
                del filters[i]
                break

    def add_filter(self, id: str, value: str) -> None:
        filters = self.state.get("filters", [])
        filters.append(
            {
                "id": id,
                "value": value,
            }
        )
        self.state["filters"] = filters

    def sort_by(self, value: str) -> None:
        self.state["sort-by"] = value

    #
    # Filtering
    #
    def get_filters(self) -> list[dict]:
        """Build filter options using efficient DISTINCT queries.

        Instead of loading all events and extracting distinct values in Python,
        we query distinct values directly from the database for each filter column.
        """
        result = []
        for spec in FILTER_SPECS:
            filter_id = spec["id"]
            label = spec["label"]
            column_name = spec["column"]
            label_func: Callable[[str], str] | None = spec.get("label_function")

            # Get distinct values for this column
            distinct_values = _get_distinct_values(column_name)
            if spec.get("multi"):
                distinct_values = _flatten(distinct_values)
            distinct_values = _sorted_like_taxonomy(
                distinct_values, spec.get("taxonomy")
            )

            # Build options list
            options = []
            for value in distinct_values:
                if not value:  # Skip empty values
                    continue
                option_label = label_func(value) if label_func else value
                options.append({"id": value, "label": option_label})

            result.append({"id": filter_id, "label": label, "options": options})

        return result


def _flatten(rows: list[list[str]]) -> list[str]:
    """Réduire les listes d'une colonne `TagList` aux valeurs présentes.

    `DISTINCT` a porté sur le texte entier de la colonne : deux
    événements aux fonctions `|A|B|` et `|A|C|` en sortent tous les
    deux, et `A` est là deux fois. Le dédoublonnage se fait donc ici.

    Aucune ligne n'est `None` : la requête écarte les colonnes nulles, et
    `TagList` rend `[]` plutôt que `None`.
    """
    return sorted({value for row in rows for value in row})


def _sorted_like_taxonomy(values: list[str], taxonomy: str | None) -> list[str]:
    """Order `values` like `taxonomy`, unknown values last.

    A filter without a `taxonomy` in its spec keeps the order it came
    with (the DISTINCT query sorts alphabetically).
    """
    if not taxonomy:
        return values
    order = get_taxonomy(taxonomy)
    if not order:
        return values
    rank = {value: i for i, value in enumerate(order)}
    return sorted(values, key=lambda value: rank.get(value, len(order)))


def _get_distinct_values(column_name: str) -> list[str]:
    """Query distinct non-empty values for a column from public events.

    Only returns values from events that are either:
    - Starting in the future, or
    - Currently ongoing (end_date >= today)

    This ensures filter options only show values that will return results.

    Toutes les colonnes filtrées sont désormais de vraies colonnes :
    `departement` et `ville` étaient des propriétés hybrides dont le SQL
    n'existait que sur PostgreSQL, et la requête était enveloppée d'un
    `except OperationalError` qui rendait le filtre vide plutôt que
    cassé (audit du 2026-09-01).
    """
    import arrow

    column: InstrumentedAttribute = getattr(EventPost, column_name)
    today = arrow.now().floor("day")

    stmt = (
        sa.select(column)
        .where(EventPost.status == PublicationStatus.PUBLIC)
        .where(column.is_not(None))
        # Only include events that haven't ended yet
        .where(
            sa.or_(
                EventPost.start_datetime >= today,
                EventPost.end_datetime >= today,
            )
        )
        .distinct()
        .order_by(column)
    )

    # `!= ""` seulement sur les colonnes de texte. Sur une colonne
    # d'énumération, PostgreSQL transtype `''` vers le type natif et
    # lève `InvalidTextRepresentation` : la page /events/ entière
    # renvoie 500. SQLite, qui stocke l'énumération en `VARCHAR`,
    # accepte la comparaison — le défaut serait donc invisible à la
    # suite SQLite. L'erreur est en outre une `DataError`, qui laisse
    # la transaction PostgreSQL avortée : le filtre *suivant* de la
    # boucle échouerait à son tour.
    if not isinstance(column.type, sa.Enum):
        stmt = stmt.where(column != "")

    return list(db.session.scalars(stmt))
