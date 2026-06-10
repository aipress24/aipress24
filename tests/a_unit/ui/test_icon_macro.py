# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.ui.macros.icon`.

The `icon()` macro reads SVG files from `<project_root>/icons/svg/<type>/<name>.svg`,
strips the hard-coded 24×24 sizing, injects HTML attributes, and
returns the result wrapped in `Markup` so the autoescape policy
doesn't show it as literal text (the contract from `app.flask.lib.macros.macro`).

Real icons are committed to the repo under `icons/svg/{solid,outline,lucide}/` ;
tests exercise the happy + edge paths against those, no fixtures
needed.
"""

from __future__ import annotations

from markupsafe import Markup

from app.ui.macros.icon import icon


class TestIconEmpty:
    def test_empty_name_returns_empty_markup(self):
        result = icon("")
        assert result == Markup("")
        # The decorator's wrap is what gives us Markup ; the body
        # returns Markup("") and the wrapper preserves it.
        assert isinstance(result, Markup)


class TestIconNotFound:
    def test_missing_icon_returns_placeholder_comment(self):
        """A name that doesn't resolve to a file produces a clearly
        visible HTML comment, not a 500. Pin so a future « strict mode »
        change doesn't silently start crashing the wall."""
        result = icon("absolutely-no-such-icon")
        assert "icon not found" in result
        assert "absolutely-no-such-icon" in result

    def test_missing_icon_with_explicit_type(self):
        result = icon("ghost", type="outline")
        assert "outline/ghost" in result


class TestIconSeparatorDispatch:
    def test_slash_separator_sets_type_then_name(self):
        """`name="solid/foo"` → type=solid, name=foo. Pin so a future
        rewrite doesn't flip the order."""
        result = icon("solid/nonexistent_xyz")
        assert "solid/nonexistent_xyz" in result
        assert "icon not found" in result

    def test_at_separator_sets_name_then_type(self):
        """`name="bar@outline"` → name=bar, type=outline. The `@` shape
        is the inverse of the slash shape — pin both."""
        result = icon("nonexistent_xyz@outline")
        assert "outline/nonexistent_xyz" in result
        assert "icon not found" in result


class TestIconHappyPath:
    """Real icon committed under `icons/svg/solid/academic-cap.svg`.
    Pin the transformations that the macro does on the file's content :
    strip width/height, inject attrs, prepend the source comment."""

    def test_strips_hardcoded_24px_dimensions(self):
        """The macro lets the surrounding CSS class drive sizing —
        leaving width="24" / height="24" in would fight Tailwind classes
        on the call site."""
        result = icon("academic-cap")
        assert 'width="24"' not in result
        assert 'height="24"' not in result

    def test_prepends_icon_source_comment(self):
        """The HTML comment helps debugging — quickly identifies which
        icon family + name was rendered. Pin so a refactor doesn't
        silently strip it."""
        result = icon("academic-cap")
        assert "<!-- icon: solid/academic-cap -->" in result

    def test_returns_markup_so_autoescape_does_not_eat_it(self):
        """Family of bug #0162 / #0126 — the macro wrapper guarantees
        Markup; verify it's preserved."""
        result = icon("academic-cap")
        assert isinstance(result, Markup)

    def test_class_attr_promoted_from_underscore_kwarg(self):
        """`_class` is the legacy kw name (since `class` is reserved) —
        the macro mirrors it into the `class` attribute on the SVG."""
        result = icon("academic-cap", _class="w-6 h-6 text-blue-500")
        assert "class='w-6 h-6 text-blue-500'" in result

    def test_kwargs_get_kebab_cased_into_attributes(self):
        """Tailwind-style `aria_label='X'` → `aria-label='X'`. Pin so
        the macro stays compatible with both the python kwarg style and
        the HTML attribute style."""
        result = icon("academic-cap", aria_label="example")
        assert "aria-label='example'" in result

    def test_renders_outline_when_explicit_type(self):
        # An outline-tier name might not exist for every icon — use a
        # known-present outline icon.
        result = icon("academic-cap", type="outline")
        # Either the file exists (commented header) or doesn't (comment
        # placeholder). Either way, the type+name routing is exercised.
        assert "outline/academic-cap" in result
