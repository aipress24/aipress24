# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the filter primitives in
`app.modules.swork.components.base`.

The module defines a tiny in-house mini-framework for filtered list
components :

- `FilterOption` — a `(option, code)` pair that the template renders.
  It's frozen so it can live in a Set and be used as a dict key ; it's
  ordered so that the build-from-objects path can deterministically
  `sorted(...)` the values. Only the human-readable `option` field is
  used for equality/order — the `code` is "metadata" attached for the
  filter handler.

- `Filter` — the abstract base. Subclasses declare an `id`, a `label`,
  a `selector` (str-attr-name OR callable), and override `apply()`.
  The base ctor knows how to derive `options` from a list of objects
  by calling the selector and deduping/sorting. `active_options(state)`
  is the pure read-the-state helper that maps a checkbox state dict
  back to the chosen option values.

- `FilterByCity` / `FilterByDept` — concrete subclasses for
  `Addressable` (mixin on Organisation / User / etc.). Their
  `selector(obj)` is defensive : when called with a non-Addressable
  it returns `""` rather than crashing — important because the
  generic UI may feed in heterogeneous objects.

This file pins the contract so a refactor (e.g. switching
`FilterOption` away from `@dataclass(frozen=True, order=True)`, or
making `Filter.__init__` accept a different selector shape) surfaces
immediately rather than breaking the directory filters at runtime.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.models.organisation import Organisation
from app.modules.swork.components.base import (
    Filter,
    FilterByCity,
    FilterByDept,
    FilterOption,
)


class _FakeAddr:
    """Duck-typed stand-in for a non-Addressable object.

    Used to exercise the defensive `isinstance(obj, Addressable)` branch
    of `FilterByCity.selector` / `FilterByDept.selector`."""

    def __init__(self, city: str = "", dept_code: str = "") -> None:
        self.city = city
        self.dept_code = dept_code


# ── FilterOption ─────────────────────────────────────────────────────


class TestFilterOption:
    """Pin the dataclass contract : frozen, ordered, equality+hash on
    `option` only, `__str__` returns the human label.

    These are not stylistic — they enable concrete usage patterns :
    the build-from-objects path puts options in a `set` then `sorted()`s
    them ; the template iterates and renders `{{ option }}` directly."""

    def test_default_code_is_empty_string(self):
        """The `code` field defaults to `""` so callers that don't
        carry a code (plain string-like usage) can construct without
        boilerplate."""
        opt = FilterOption("Paris")
        assert opt.option == "Paris"
        assert opt.code == ""

    def test_str_returns_option_not_code(self):
        """`__str__` returns the human label. The active-filter UI
        chips and the comparison in `action_remove_filter` both rely
        on `str(option) == option_value` to match."""
        opt = FilterOption(option="Paris", code="75")
        assert str(opt) == "Paris"

    def test_equality_ignores_code(self):
        """Equality is on `option` only (the `code` field is
        `compare=False`). Two FilterOption with the same label but
        different codes are interchangeable for set-deduping."""
        assert FilterOption("Paris", "75") == FilterOption("Paris", "")
        assert FilterOption("Paris", "75") == FilterOption("Paris", "X")

    def test_inequality_when_option_differs(self):
        assert FilterOption("Paris", "75") != FilterOption("Lyon", "75")

    def test_hashable_and_hash_ignores_code(self):
        """Frozen dataclasses are hashable. Because `code` is
        `compare=False`, hash only sees `option` — required so set
        deduping in `Filter.__init__` works for FilterOption values."""
        a = FilterOption("Paris", "75")
        b = FilterOption("Paris", "")
        assert hash(a) == hash(b)
        assert {a, b} == {a}

    def test_ordered_sorts_by_option_attribute(self):
        """`order=True` provides `<` so `sorted(...)` works. Pin
        that sort is by `option` (the only compared field) so the
        UI dropdown shows alphabetical labels regardless of code."""
        options = [
            FilterOption("Paris", "75"),
            FilterOption("Lyon", "69"),
            FilterOption("Marseille", "13"),
        ]
        assert sorted(options) == [
            FilterOption("Lyon", "69"),
            FilterOption("Marseille", "13"),
            FilterOption("Paris", "75"),
        ]

    def test_frozen_disallows_attribute_assignment(self):
        """`frozen=True` — pin so a refactor that drops it breaks
        loudly rather than silently allowing template-time mutation."""
        opt = FilterOption("Paris", "75")
        with pytest.raises((AttributeError, Exception)):
            opt.option = "Lyon"  # type: ignore[misc]


# ── Filter (base class) ──────────────────────────────────────────────


class _StrSelectorObj:
    """Tiny object with a `name` attr — used to exercise the
    string-selector branch of `Filter.__init__`."""

    def __init__(self, name: str) -> None:
        self.name = name


class _StringSelectorFilter(Filter):
    """Filter subclass driving the `isinstance(selector, str)` branch."""

    id = "name"
    label = "Name"
    selector = "name"  # type: ignore[assignment]


class _CallableSelectorFilter(Filter):
    """Filter subclass driving the `callable(selector)` branch."""

    id = "callable"
    label = "Callable"

    def selector(self, obj: Any) -> str:
        return str(getattr(obj, "name", ""))


class _BadSelectorFilter(Filter):
    """Filter subclass with a nonsense selector type — exercises
    the `TypeError` branch."""

    id = "bad"
    label = "Bad"
    selector = 12345  # type: ignore[assignment]


class TestFilterBase:
    """Pin the contract of the abstract base class — the parts that
    aren't `@abstractmethod` and therefore *should* keep working
    even as concrete subclasses evolve."""

    def test_apply_on_base_raises_not_implemented(self):
        """`apply` is the extension point — must raise to force
        subclasses to implement, otherwise stmt would silently pass
        through and filtering would be a no-op."""
        f = Filter()
        with pytest.raises(NotImplementedError):
            f.apply(select(Organisation), {})

    def test_active_options_returns_only_checked(self):
        """The fundamental state->options mapping : index `i` is
        checked iff `state[str(i)]` is truthy. Pin the ordering
        (preserves `self.options` order, not state-dict order)."""
        f = Filter()
        f.options = ["A", "B", "C", "D"]
        state = {"0": False, "1": True, "2": False, "3": True}
        assert f.active_options(state) == ["B", "D"]

    def test_active_options_all_false_returns_empty(self):
        f = Filter()
        f.options = ["A", "B"]
        assert f.active_options({"0": False, "1": False}) == []

    def test_active_options_all_true_returns_all(self):
        f = Filter()
        f.options = ["A", "B", "C"]
        state = {"0": True, "1": True, "2": True}
        assert f.active_options(state) == ["A", "B", "C"]

    def test_active_options_preserves_options_order(self):
        """The order of returned active options matches the order
        of `self.options`, regardless of state-dict iteration order.
        Pin so a Python-version dict-ordering shift can't reshuffle
        the active-filter chips in the UI."""
        f = Filter()
        f.options = [
            FilterOption("Apple", "a"),
            FilterOption("Banana", "b"),
            FilterOption("Cherry", "c"),
        ]
        state = {"2": True, "0": True, "1": False}
        active = f.active_options(state)
        assert active == [FilterOption("Apple", "a"), FilterOption("Cherry", "c")]

    def test_init_with_no_objects_keeps_options_empty(self):
        """Default ctor (no objects) leaves options as `[]` — the
        usual path when a subclass populates options via class attr."""
        f = _StringSelectorFilter()
        assert f.options == []

    def test_init_with_objects_string_selector(self):
        """The string-selector branch reads `getattr(obj, selector)`
        for each object and `sorted({...})`s the results."""
        objs = [_StrSelectorObj("z"), _StrSelectorObj("a"), _StrSelectorObj("m")]
        f = _StringSelectorFilter(objs)
        assert f.options == ["a", "m", "z"]

    def test_init_with_objects_string_selector_dedupes(self):
        """Duplicates collapse via `set(...)` before sorting."""
        objs = [
            _StrSelectorObj("Paris"),
            _StrSelectorObj("Lyon"),
            _StrSelectorObj("Paris"),
        ]
        f = _StringSelectorFilter(objs)
        assert f.options == ["Lyon", "Paris"]

    def test_init_with_objects_callable_selector_strips_falsy(self):
        """The callable branch filters out falsy values (`""`,
        `None`) before assigning options. Pin so a future regression
        that pollutes filter dropdowns with blank entries is caught."""
        objs = [
            _StrSelectorObj("Paris"),
            _StrSelectorObj(""),
            _StrSelectorObj("Lyon"),
        ]
        f = _CallableSelectorFilter(objs)
        assert "" not in f.options
        assert set(f.options) == {"Paris", "Lyon"}

    def test_init_with_invalid_selector_raises_typeerror(self):
        """A selector that's neither str nor callable explodes
        loudly — protects against silent misconfig in subclasses."""
        with pytest.raises(TypeError, match="Invalid selector"):
            _BadSelectorFilter([_StrSelectorObj("x")])

    def test_init_with_empty_objects_list_keeps_options(self):
        """An empty list short-circuits before reading the
        selector — pin so the no-data path doesn't crash on
        misconfigured selectors."""
        f = _BadSelectorFilter([])
        assert f.options == []


# ── FilterByCity ─────────────────────────────────────────────────────


class _AddressableUser(
    __import__("app.models.mixins", fromlist=["Addressable"]).Addressable
):
    """Minimal `Addressable` subclass for selector tests.

    We don't need SQLAlchemy mapping here — we just need an instance
    that passes `isinstance(obj, Addressable)`."""

    def __init__(self, city: str = "", dept_code: str = "") -> None:
        self.city = city
        self.dept_code = dept_code


class TestFilterByCity:
    """`FilterByCity` filters Addressable objects by their `city`
    attribute. Pin the id/label (used by the UI to render the
    checkbox group) and the defensive non-Addressable branch."""

    def test_id_and_label(self):
        f = FilterByCity()
        assert f.id == "city"
        assert f.label == "Ville"

    def test_selector_reads_city_attribute(self):
        """Happy path : Addressable object -> its city as string."""
        f = FilterByCity()
        user = _AddressableUser(city="Paris")
        assert f.selector(user) == "Paris"

    def test_selector_returns_empty_string_for_non_addressable(self):
        """Defensive branch — anything that isn't an Addressable
        gets `""` back. Pin so heterogeneous lists don't crash the
        options-building path."""
        f = FilterByCity()
        assert f.selector(_FakeAddr(city="Paris")) == ""
        assert f.selector(object()) == ""
        assert f.selector("just-a-string") == ""

    def test_selector_coerces_city_to_string(self):
        """`str(obj.city)` — even if a model migration leaves a
        non-str value (None, an enum) the selector won't crash."""
        f = FilterByCity()
        user = _AddressableUser()
        user.city = None  # type: ignore[assignment]
        assert f.selector(user) == "None"

    def test_apply_with_no_active_options_returns_stmt_unchanged(self):
        """No checkboxes ticked == no-op. Pin the SQL passthrough
        so that an unused filter doesn't accidentally add a
        WHERE 1=0 to the directory query."""
        f = FilterByCity()
        f.options = ["Paris", "Lyon"]
        stmt = select(Organisation)
        result = f.apply(stmt, {"0": False, "1": False})
        assert str(result) == str(stmt)

    def test_apply_with_active_options_narrows_stmt(self):
        """At least one option ticked -> a new statement with an
        added `WHERE city IN (...)` clause. We compare as strings
        because SQLAlchemy statement equality is by identity."""
        f = FilterByCity()
        f.options = ["Paris", "Lyon"]
        stmt = select(Organisation)
        result = f.apply(stmt, {"0": True, "1": False})
        # New stmt has an IN clause that the bare stmt doesn't.
        assert "IN" in str(result).upper()
        assert str(result) != str(stmt)


# ── FilterByDept ─────────────────────────────────────────────────────


class TestFilterByDept:
    """Same pattern as FilterByCity but on the `dept_code` attribute.
    The two classes are deliberately almost-identical — pin them
    independently so a refactor that tries to DRY them doesn't
    accidentally swap a field."""

    def test_id_and_label(self):
        f = FilterByDept()
        assert f.id == "dept"
        assert f.label == "Département"

    def test_selector_reads_dept_code_attribute(self):
        f = FilterByDept()
        user = _AddressableUser(dept_code="75")
        assert f.selector(user) == "75"

    def test_selector_returns_empty_string_for_non_addressable(self):
        f = FilterByDept()
        assert f.selector(_FakeAddr(dept_code="75")) == ""
        assert f.selector(object()) == ""

    def test_selector_specifically_reads_dept_code_not_city(self):
        """Cross-check against copy-paste : `FilterByDept.selector`
        reads `dept_code`, not `city`. Pin so a future refactor
        that DRYs the two classes can't silently swap the field."""
        f = FilterByDept()
        user = _AddressableUser(city="Paris", dept_code="75")
        assert f.selector(user) == "75"
        assert f.selector(user) != "Paris"

    def test_apply_with_no_active_options_returns_stmt_unchanged(self):
        f = FilterByDept()
        f.options = ["75", "69"]
        stmt = select(Organisation)
        result = f.apply(stmt, {"0": False, "1": False})
        assert str(result) == str(stmt)

    def test_apply_with_active_options_narrows_stmt(self):
        f = FilterByDept()
        f.options = ["75", "69"]
        stmt = select(Organisation)
        result = f.apply(stmt, {"0": True, "1": True})
        assert "IN" in str(result).upper()
        assert str(result) != str(stmt)


# ── End-to-end : build a filter from objects ─────────────────────────


class TestFilterByCityFromObjects:
    """Cross-check the `__init__(objects)` path on the real
    FilterByCity subclass : selector is a method (callable), so the
    callable branch is taken, falsy values are stripped, results
    are sorted."""

    @pytest.mark.parametrize(
        ("subclass", "attr"),
        [
            (FilterByCity, "city"),
            (FilterByDept, "dept_code"),
        ],
    )
    def test_options_built_from_objects(self, subclass, attr):
        users = [
            _AddressableUser(**{attr: "B"}),
            _AddressableUser(**{attr: "A"}),
            _AddressableUser(**{attr: "C"}),
            _AddressableUser(**{attr: "A"}),  # dup
        ]
        f = subclass(users)
        assert f.options == ["A", "B", "C"]

    def test_non_addressable_objects_yield_empty_strings_stripped(self):
        """A list containing non-Addressable objects gives
        empty-string selector results, which the callable branch
        strips out — pin so a heterogeneous source list doesn't
        crash or insert blank dropdown entries."""
        users = [
            _AddressableUser(city="Paris"),
            _FakeAddr(city="Lyon"),  # not an Addressable
        ]
        f = FilterByCity(users)
        assert f.options == ["Paris"]
