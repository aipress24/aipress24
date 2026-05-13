# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Coverage for `app.services.html_sanitize.sanitize_html`.

Every entry is an attack vector or an honest UI case. New attempted
bypasses should land here, not in production templates.
"""

from __future__ import annotations

from markupsafe import Markup

from app.services.html_sanitize import sanitize_html


class TestSanitizeRemovesDangerous:
    def test_script_tag_dropped(self):
        # The `<script>` opening tag is stripped. Its inner text may
        # remain (as visible text now, not executable code) — that's
        # acceptable: the security guarantee is "no live <script>",
        # not "script content invisible".
        out = sanitize_html("<script>alert(1)</script>")
        assert "<script" not in out
        assert "</script>" not in out

    def test_inline_event_handler_dropped(self):
        out = sanitize_html('<a href="https://ok" onclick="alert(1)">x</a>')
        assert "onclick" not in out
        assert "alert" not in out

    def test_onerror_on_image_dropped(self):
        out = sanitize_html('<img src="https://ok/x.png" onerror="alert(1)">')
        assert "onerror" not in out
        assert "alert" not in out

    def test_javascript_href_rejected(self):
        # `<a href="javascript:...">` must lose its href.
        out = sanitize_html('<a href="javascript:alert(1)">x</a>')
        assert "javascript:" not in out

    def test_javascript_href_obfuscated_rejected(self):
        # Control-char obfuscation: an attacker pads the scheme with
        # tabs/newlines to bypass naive prefix checks.
        out = sanitize_html('<a href="\tjavascript:alert(1)">x</a>')
        assert "javascript" not in out.lower() or "alert" not in out

    def test_data_uri_on_anchor_rejected(self):
        # data: on <a> can carry text/html with embedded scripts.
        out = sanitize_html('<a href="data:text/html,<script>x</script>">x</a>')
        assert "data:" not in out

    def test_data_uri_on_image_also_rejected(self):
        # data: is excluded across the board in this app: Trix uploads
        # go to object storage so inline base64 isn't a real UI need,
        # and accepting it widens the attack surface (image/svg+xml
        # data URIs can carry inline scripts).
        out = sanitize_html(
            '<img src="data:image/png;base64,iVBORw=" alt="ok">'
        )
        assert "data:" not in out

    def test_style_tag_dropped(self):
        # <style> CSS can be a vector (expression()) — strip it.
        out = sanitize_html("<style>body{background:url(x)}</style>hello")
        assert "<style>" not in out
        assert "hello" in out

    def test_iframe_dropped(self):
        out = sanitize_html('<iframe src="https://evil"></iframe>')
        assert "<iframe" not in out

    def test_form_dropped(self):
        out = sanitize_html('<form action="https://evil"><input></form>')
        assert "<form" not in out


class TestSanitizeKeepsLegitimateMarkup:
    def test_basic_formatting_kept(self):
        out = sanitize_html("<p><b>hello</b> <i>world</i></p>")
        assert "<b>hello</b>" in out
        assert "<i>world</i>" in out

    def test_external_link_kept(self):
        out = sanitize_html('<a href="https://example.com">click</a>')
        assert 'href="https://example.com"' in out

    def test_mailto_link_kept(self):
        out = sanitize_html('<a href="mailto:x@y.com">mail</a>')
        assert 'href="mailto:x@y.com"' in out

    def test_image_with_alt_kept(self):
        out = sanitize_html(
            '<img src="https://example.com/x.png" alt="caption" width="80">'
        )
        assert 'src="https://example.com/x.png"' in out
        assert 'alt="caption"' in out
        assert 'width="80"' in out

    def test_trix_figure_attachment_kept(self):
        # Trix wraps image attachments in <figure data-trix-attachment=…>.
        # We need the data-trix-* attributes preserved so the renderer
        # can re-attach styling.
        html = (
            '<figure data-trix-attachment="{}" '
            'data-trix-content-type="image/png" '
            'class="attachment attachment--preview">'
            '<img src="https://ok/x.png" alt=""><figcaption>x</figcaption>'
            "</figure>"
        )
        out = sanitize_html(html)
        assert "data-trix-attachment" in out
        assert "data-trix-content-type" in out
        assert "<figcaption>" in out


class TestJinjaFilterWiring:
    """The `|sanitize` filter must be registered on the Flask app so
    templates can use it directly. Pinned because the registration
    (in `app.flask.main.register_filters`) is easy to forget when
    refactoring."""

    def test_filter_registered_on_app(self, app):
        assert "sanitize" in app.jinja_env.filters, (
            "`|sanitize` filter is not registered. See "
            "`app.flask.main.register_filters`."
        )
        # And calling it does the expected thing.
        filt = app.jinja_env.filters["sanitize"]
        out = filt("<script>x</script><b>kept</b>")
        assert "<script" not in out
        assert "<b>kept</b>" in out

    def test_filter_renders_from_template(self, app):
        """End-to-end through a Jinja string template."""
        template = app.jinja_env.from_string(
            "{{ html|sanitize }}"
        )
        out = template.render(
            html='<a href="javascript:alert(1)">x</a><b>ok</b>'
        )
        assert "javascript:" not in out
        assert "<b>ok</b>" in out


class TestSanitizeContract:
    def test_returns_markup_type(self):
        # Filter must return Markup so chaining `|safe` is a no-op
        # and Jinja autoescape leaves it alone in templates.
        result = sanitize_html("<p>x</p>")
        assert isinstance(result, Markup)

    def test_none_returns_empty_markup(self):
        out = sanitize_html(None)
        assert isinstance(out, Markup)
        assert str(out) == ""

    def test_plain_text_unchanged(self):
        out = sanitize_html("just some text")
        assert "just some text" in out

    def test_already_escaped_chars_preserved(self):
        # `&lt;` should not be decoded back into `<`.
        out = sanitize_html("&lt;script&gt;alert(1)&lt;/script&gt;")
        assert "<script>" not in out
        # Either kept as entities or escaped — both safe.
