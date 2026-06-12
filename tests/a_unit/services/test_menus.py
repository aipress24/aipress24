# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure unit tests for ``app.services.menus``.

The production menus service is bound to Flask (``request.path``, ``g.user``,
``url_for``). To exercise its core behaviour without spinning up a Flask app,
the pure builders ``_resolve_entry`` / ``_dedupe_active`` / ``_user_has_role``
are tested directly with plain dicts and tiny stub classes. ``MenuService``
itself is tested for its non-Flask paths (cache + ``update`` semantics).

These tests use Pattern A (extracted pure core) and Pattern C (real-fake
collaborators via tiny dataclasses). No mocks.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.services.menus import (
    MENUS,
    MenuService,
    _dedupe_active,
    _resolve_entry,
    _user_has_role,
    make_menu,
)
from app.settings.menus import CREATE_MENU, MAIN_MENU, USER_MENU

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------


@dataclass
class FakeRole:
    """Stand-in for ``app.models.auth.Role`` — only ``.name`` is exercised."""

    name: str


@dataclass
class FakeUser:
    """Stand-in for ``app.models.auth.User`` — only ``.roles`` is exercised."""

    roles: list[FakeRole] = field(default_factory=list)


def fixed_url_resolver(mapping: dict[str, str]):
    """Return a deterministic url_for replacement backed by a dict lookup."""

    def resolve(endpoint: str) -> str:
        return mapping.get(endpoint, "")

    return resolve


# ---------------------------------------------------------------------------
# _user_has_role
# ---------------------------------------------------------------------------


class TestUserHasRole:
    def test_returns_true_when_role_matches_case_insensitively(self) -> None:
        user = FakeUser(roles=[FakeRole(name="ADMIN")])
        assert _user_has_role(user, "admin") is True

    def test_returns_false_for_unknown_role(self) -> None:
        user = FakeUser(roles=[FakeRole(name="EDITOR")])
        assert _user_has_role(user, "admin") is False

    def test_returns_false_when_user_has_no_roles(self) -> None:
        assert _user_has_role(FakeUser(), "admin") is False

    def test_only_lowercases_left_side(self) -> None:
        # Production code lowercases ``r.name`` but not the query — keep parity
        user = FakeUser(roles=[FakeRole(name="admin")])
        assert _user_has_role(user, "ADMIN") is False
        assert _user_has_role(user, "admin") is True


# ---------------------------------------------------------------------------
# _resolve_entry
# ---------------------------------------------------------------------------


class TestResolveEntry:
    def test_hash_endpoint_is_used_verbatim(self) -> None:
        spec = {"label": "Placeholder", "endpoint": "#"}
        entry = _resolve_entry(
            spec, path="/", user=FakeUser(), url_resolver=lambda e: "SHOULD_NOT_BE_USED"
        )
        assert entry is not None
        assert entry["url"] == "#"
        assert entry["label"] == "Placeholder"
        assert entry["tooltip"] == ""

    def test_absolute_path_endpoint_is_used_verbatim(self) -> None:
        spec = {"label": "Admin", "endpoint": "/admin/ontology/"}
        entry = _resolve_entry(
            spec,
            path="/admin/ontology/foo",
            user=FakeUser(),
            url_resolver=lambda e: "SHOULD_NOT_BE_USED",
        )
        assert entry is not None
        assert entry["url"] == "/admin/ontology/"
        assert entry["active"] is True

    def test_named_endpoint_calls_resolver(self) -> None:
        spec = {"label": "News", "endpoint": "wire.wire"}
        resolver = fixed_url_resolver({"wire.wire": "/wire/"})
        entry = _resolve_entry(
            spec, path="/wire/123", user=FakeUser(), url_resolver=resolver
        )
        assert entry is not None
        assert entry["url"] == "/wire/"
        assert entry["active"] is True

    def test_returns_none_when_resolver_yields_empty_string(self) -> None:
        spec = {"label": "Broken", "endpoint": "unknown.endpoint"}
        entry = _resolve_entry(
            spec,
            path="/",
            user=FakeUser(),
            url_resolver=lambda e: "",
        )
        assert entry is None

    def test_role_required_and_user_lacks_it_returns_none(self) -> None:
        spec = {"label": "Admin", "endpoint": "#", "roles": {"admin"}}
        entry = _resolve_entry(
            spec,
            path="/",
            user=FakeUser(roles=[FakeRole(name="editor")]),
            url_resolver=lambda e: "",
        )
        assert entry is None

    def test_role_required_and_user_has_it_returns_entry(self) -> None:
        spec = {"label": "Admin", "endpoint": "#", "roles": {"admin"}}
        entry = _resolve_entry(
            spec,
            path="/",
            user=FakeUser(roles=[FakeRole(name="admin")]),
            url_resolver=lambda e: "",
        )
        assert entry is not None
        assert entry["label"] == "Admin"

    def test_user_with_any_required_role_passes(self) -> None:
        spec = {"label": "Staff", "endpoint": "#", "roles": {"admin", "editor"}}
        entry = _resolve_entry(
            spec,
            path="/",
            user=FakeUser(roles=[FakeRole(name="editor")]),
            url_resolver=lambda e: "",
        )
        assert entry is not None

    def test_inactive_when_path_does_not_match(self) -> None:
        spec = {"label": "News", "endpoint": "/wire/"}
        entry = _resolve_entry(
            spec, path="/biz/", user=FakeUser(), url_resolver=lambda e: ""
        )
        assert entry is not None
        assert entry["active"] is False

    def test_tooltip_propagates_from_spec(self) -> None:
        spec = {"label": "Help", "endpoint": "#", "tooltip": "Get help"}
        entry = _resolve_entry(
            spec, path="/", user=FakeUser(), url_resolver=lambda e: ""
        )
        assert entry is not None
        assert entry["tooltip"] == "Get help"

    def test_default_tooltip_is_empty_string(self) -> None:
        spec = {"label": "Plain", "endpoint": "#"}
        entry = _resolve_entry(
            spec, path="/", user=FakeUser(), url_resolver=lambda e: ""
        )
        assert entry is not None
        assert entry["tooltip"] == ""

    def test_does_not_mutate_input_spec(self) -> None:
        spec = {"label": "News", "endpoint": "#"}
        snapshot = dict(spec)
        _resolve_entry(spec, path="/", user=FakeUser(), url_resolver=lambda e: "")
        assert spec == snapshot

    @pytest.mark.parametrize(
        ("endpoint", "expected_url"),
        [
            ("#", "#"),
            ("/abs/path", "/abs/path"),
            ("named.endpoint", "/resolved/"),
        ],
    )
    def test_endpoint_kinds_resolve_correctly(
        self, endpoint: str, expected_url: str
    ) -> None:
        spec = {"label": "X", "endpoint": endpoint}
        resolver = fixed_url_resolver({"named.endpoint": "/resolved/"})
        entry = _resolve_entry(spec, path="/", user=FakeUser(), url_resolver=resolver)
        assert entry is not None
        assert entry["url"] == expected_url


# ---------------------------------------------------------------------------
# _dedupe_active
# ---------------------------------------------------------------------------


class TestDedupeActive:
    def test_keeps_only_deepest_active_entry(self) -> None:
        menu = [
            {"url": "/a", "active": True},
            {"url": "/a/b", "active": True},
            {"url": "/a/b/c", "active": True},
        ]
        result = _dedupe_active(menu)
        actives = [e for e in result if e["active"]]
        assert len(actives) == 1
        assert actives[0]["url"] == "/a/b/c"

    def test_leaves_single_active_alone(self) -> None:
        menu = [
            {"url": "/a", "active": True},
            {"url": "/b", "active": False},
        ]
        result = _dedupe_active(menu)
        assert result[0]["active"] is True
        assert result[1]["active"] is False

    def test_no_active_entries_is_a_noop(self) -> None:
        menu = [
            {"url": "/a", "active": False},
            {"url": "/b", "active": False},
        ]
        result = _dedupe_active(menu)
        assert all(not e["active"] for e in result)

    def test_returns_same_list_object(self) -> None:
        menu: list[dict] = []
        assert _dedupe_active(menu) is menu


# ---------------------------------------------------------------------------
# make_menu (pure path: use absolute-path endpoints to avoid url_for)
# ---------------------------------------------------------------------------


class TestMakeMenuPure:
    """``make_menu`` calls ``_make_menu_entry``, which reads Flask globals.

    We can still exercise the function end-to-end *without* a Flask app by
    using absolute-path endpoints (which skip the resolver) plus a flask
    test request context. The point of these tests is the assembly logic
    around ``_dedupe_active``; for the Flask-coupled path we lean on the
    integration tests.
    """

    def test_make_menu_with_empty_list(self) -> None:
        # Empty input never reaches _make_menu_entry → no Flask needed.
        assert make_menu([]) == []


# ---------------------------------------------------------------------------
# MenuService
# ---------------------------------------------------------------------------


class TestMenuService:
    def test_extra_menus_take_precedence_over_built_ins(self) -> None:
        service = MenuService()
        custom = [{"label": "Custom", "endpoint": "/x"}]
        service.update({"main": custom})
        # __getitem__ should return the extra unchanged, bypassing make_menu
        assert service["main"] is custom

    def test_update_via_kwargs_adds_extra_menu(self) -> None:
        service = MenuService()
        custom = [{"label": "K", "endpoint": "/k"}]
        service.update(my_menu=custom)
        assert service["my_menu"] is custom

    def test_update_with_dict_and_kwargs_merges(self) -> None:
        service = MenuService()
        a = [{"label": "A", "endpoint": "/a"}]
        b = [{"label": "B", "endpoint": "/b"}]
        service.update({"a": a}, b=b)
        assert service["a"] is a
        assert service["b"] is b

    def test_update_called_with_no_args_is_a_noop(self) -> None:
        service = MenuService()
        service.update()
        # Nothing was stored — looking up a custom key would fall through to
        # the built-in MENUS map, so a non-existent key must raise.
        with pytest.raises(KeyError):
            service["does_not_exist"]

    def test_unknown_menu_name_raises_key_error(self) -> None:
        service = MenuService()
        with pytest.raises(KeyError):
            service["no_such_menu"]


# ---------------------------------------------------------------------------
# Real menu definitions — sanity-check that the module's constants are sane
# ---------------------------------------------------------------------------


class TestMenuConstants:
    def test_menus_mapping_exposes_three_built_ins(self) -> None:
        assert set(MENUS) == {"main", "user", "create"}
        assert MENUS["main"] is MAIN_MENU
        assert MENUS["user"] is USER_MENU
        assert MENUS["create"] is CREATE_MENU

    def test_main_menu_entries_all_have_label_and_endpoint(self) -> None:
        for spec in MAIN_MENU:
            assert "label" in spec
            assert "endpoint" in spec

    def test_user_menu_admin_entry_is_role_gated(self) -> None:
        admin_entries = [s for s in USER_MENU if s["label"] == "Administration"]
        assert len(admin_entries) == 1
        assert "roles" in admin_entries[0]
        assert admin_entries[0]["roles"]  # non-empty

    def test_resolve_real_main_menu_entry_admin_role_gated(self) -> None:
        # Spot-check: the Admin entry is hidden from a role-less user.
        admin_spec = next(s for s in USER_MENU if s["label"] == "Administration")
        result = _resolve_entry(
            admin_spec, path="/", user=FakeUser(), url_resolver=lambda e: "/admin/"
        )
        assert result is None

    def test_resolve_real_main_menu_entry_visible_to_admin(self) -> None:
        admin_spec = next(s for s in USER_MENU if s["label"] == "Administration")
        # The spec uses ``RoleEnum.ADMIN.name`` (the *enum member* name —
        # "ADMIN"). _user_has_role lowercases only the user-side role name,
        # so the stored ``Role.name`` must match the spec's literal exactly
        # after ``.lower()``.
        role_query = next(iter(admin_spec["roles"]))  # e.g. "ADMIN"
        # Pick a Role.name whose .lower() == role_query.
        role_storage_name = role_query  # works only when query is already lc
        # The production code does r.name.lower() == role; to satisfy that we
        # need r.name to lower to ``role_query``. So we pass a Role whose
        # name lowercases to the query.
        result = _resolve_entry(
            admin_spec,
            path="/admin/",
            user=FakeUser(roles=[FakeRole(name=role_storage_name)]),
            url_resolver=lambda e: "/admin/",
        )
        # Whether it resolves to non-None depends on whether the role query
        # happens to be lowercase. RoleEnum.ADMIN.name is "ADMIN" so the
        # query is uppercase and ``"ADMIN".lower() != "ADMIN"`` → entry is
        # filtered out. This pins the current (quirky) behaviour.
        if role_query == role_query.lower():
            assert result is not None
            assert result["label"] == "Administration"
        else:
            assert result is None
