# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The answers to a form of the site, described and checked for programs.

A form is a list of fields. Answers are checked as the form would: each value is
in its vocabulary, or is one the member already had.
"""

from __future__ import annotations

import difflib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, NamedTuple

import sqlalchemy as sa

from app.flask.extensions import db
from app.lib.urls import is_web_url
from app.services.taxonomies import get_taxonomy_dual_select
from app.services.zip_codes import ZipCodeEntry, get_full_countries

COUNTRIES = "countries"
CITIES = "cities"
# The groups of a nested vocabulary are themselves one.
GROUPS = ".groups"
DETAIL = "_detail"

Answers = dict[str, Any]
Errors = dict[str, list[str]]


class Kind(StrEnum):
    TEXT = "text"
    FLAG = "flag"
    CHOICE = "choice"
    CHOICES = "choices"


class Choice(NamedTuple):
    value: str
    label: str
    group: str = ""


@dataclass(frozen=True)
class AnswerField:
    """A question of a form."""

    name: str
    label: str
    kind: Kind
    section: str = ""
    required: bool = False
    # A moderator must validate a change.
    moderated: bool = False
    max_length: int = 0
    max_items: int = 0
    # Any value is accepted without one.
    vocabulary: str = ""
    # The field which holds the groups of these values.
    parent: str = ""
    check: Callable[[str], str] | None = None

    def empty(self) -> Any:
        match self.kind:
            case Kind.FLAG:
                return False
            case Kind.CHOICES:
                return []
            case _:
                return ""

    def read(self, value: Any) -> Any:
        """A stored value, which may be missing or of another shape."""
        match self.kind:
            case Kind.FLAG:
                return bool(value)
            case Kind.CHOICES:
                return [value] if isinstance(value, str) and value else [*(value or ())]
            case _:
                return (value[0] if value else "") if _is_list(value) else value or ""


def check_web_url(value: str) -> str:
    return "" if is_web_url(value) else "is not an http(s) URL"


def read_answers(fields: Iterable[AnswerField], stored: Mapping[str, Any]) -> Answers:
    return {field.name: field.read(stored.get(field.name)) for field in fields}


def missing_answers(fields: Iterable[AnswerField], answers: Answers) -> list[str]:
    return [
        field.name
        for field in fields
        if field.required and field.kind is not Kind.FLAG and not answers[field.name]
    ]


def check_answers(
    fields: Sequence[AnswerField], stored: Answers, given: Mapping[str, Any]
) -> tuple[Answers, Errors]:
    """Return what the given answers change, or what is wrong with them."""
    by_name = {field.name: field for field in fields}
    errors: Errors = {
        name: ["is not a field of this form"] for name in given if name not in by_name
    }
    clean: Answers = {}
    for name, value in given.items():
        if name not in by_name:
            continue
        field = by_name[name]
        try:
            clean[name] = _normalise(field, value)
        except ValueError as exc:
            errors[name] = [str(exc)]
    answers = {**stored, **clean}
    for name in clean:
        # A change to the groups is checked against the details they hold.
        for field in (by_name[name], by_name.get(f"{name}{DETAIL}")):
            if field and (problems := _problems(field, stored, answers)):
                errors.setdefault(field.name, []).extend(
                    p for p in problems if p not in errors.get(field.name, ())
                )
    changes = {
        name: clean[name]
        for name in by_name
        if name in clean and clean[name] != stored[name]
    }
    return changes, errors


def search_vocabulary(
    name: str, *, text: str = "", country: str = "", limit: int | None = None
) -> list[Choice]:
    """The values of a vocabulary, or those holding a text."""
    if name == CITIES:
        return _search_cities(country, text, limit)
    folded = text.casefold()
    found = [
        choice
        for choice in _vocabulary(name)
        if folded in choice.value.casefold() or folded in choice.label.casefold()
    ]
    return found[:limit]


def _normalise(field: AnswerField, value: Any) -> Any:
    match field.kind:
        case Kind.FLAG:
            if not isinstance(value, bool):
                msg = "must be true or false"
                raise ValueError(msg)
            return value
        case Kind.CHOICES:
            if not _is_list(value) or not all(isinstance(v, str) for v in value):
                msg = "must be a list of texts"
                raise ValueError(msg)
            return list(dict.fromkeys(v.strip() for v in value if v.strip()))
        case _:
            if not isinstance(value, str):
                msg = "must be a text"
                raise ValueError(msg)
            return value.strip()


def _problems(field: AnswerField, stored: Answers, answers: Answers) -> list[str]:
    value = answers[field.name]
    if field.kind is Kind.FLAG:
        return []
    if not value:
        return ["is required"] if field.required else []
    problems = []
    if field.max_length and len(value) > field.max_length:
        problems.append(f"has {len(value)} characters, of {field.max_length} at most")
    if field.max_items and len(value) > field.max_items:
        problems.append(f"has {len(value)} values, of {field.max_items} at most")
    if field.check and (problem := field.check(value)):
        problems.append(problem)
    if field.vocabulary:
        problems += _vocabulary_problems(field, stored, answers)
    return problems


def _vocabulary_problems(
    field: AnswerField, stored: Answers, answers: Answers
) -> list[str]:
    kept = set(_as_list(stored[field.name]))
    country = ""
    if field.vocabulary == CITIES:
        country = answers[field.parent]
        if country != stored[field.parent]:
            kept = set()
    problems = []
    for value in _as_list(answers[field.name]):
        choice = _find(field.vocabulary, value, country)
        if choice is None:
            # A value the vocabulary has dropped since stays the member's own.
            if value not in kept:
                problems.append(_refused(field.vocabulary, value, country))
        elif (
            choice.group and field.parent and choice.group not in answers[field.parent]
        ):
            problems.append(f"{value!r} needs {choice.group!r} in {field.parent}")
    return problems


def _find(vocabulary: str, value: str, country: str) -> Choice | None:
    if vocabulary == CITIES:
        stmt = sa.select(ZipCodeEntry.label).where(
            ZipCodeEntry.iso3 == country, ZipCodeEntry.value == value
        )
        label = db.session.scalar(stmt.limit(1))
        return None if label is None else Choice(value, label)
    return next((c for c in _vocabulary(vocabulary) if c.value == value), None)


def _refused(vocabulary: str, value: str, country: str) -> str:
    if vocabulary == CITIES:
        name = value.rpartition(" / ")[2].rpartition(" ")[2]
        closest = [c.value for c in _search_cities(country, name, limit=3)]
    else:
        values = [choice.value for choice in _vocabulary(vocabulary)]
        within = [v for v in values if value.casefold() in v.casefold()]
        close = difflib.get_close_matches(value, values, n=3)
        closest = list(dict.fromkeys([*close, *within]))[:3]
    hint = f" (closest: {'; '.join(closest)})" if closest else ""
    return f"{value!r} is not an accepted value{hint}"


def _vocabulary(name: str) -> list[Choice]:
    if name == COUNTRIES:
        return [Choice(*country) for country in get_full_countries()]
    taxonomy = get_taxonomy_dual_select(name.removesuffix(GROUPS))
    if name.endswith(GROUPS):
        return [Choice(*group) for group in taxonomy["field1"]]
    return [
        Choice(value, label, group)
        for group, values in taxonomy["field2"].items()
        for value, label in values
    ]


def _search_cities(country: str, text: str, limit: int | None) -> list[Choice]:
    if not country or not text:
        return []
    stmt = (
        sa.select(ZipCodeEntry.value, ZipCodeEntry.label)
        .where(
            ZipCodeEntry.iso3 == country,
            ZipCodeEntry.label.icontains(text, autoescape=True),
        )
        .order_by(ZipCodeEntry.label)
        .limit(limit)
    )
    return [Choice(*row) for row in db.session.execute(stmt)]


def _as_list(value: str | list[str]) -> list[str]:
    return value if isinstance(value, list) else [value]


def _is_list(value: Any) -> bool:
    return isinstance(value, (list, tuple))
