# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The stored extension decides what `/media` serves.

`/media/<name>` derives the Content-Type from the stored suffix. Were the
uploader's own suffix kept verbatim, a member who named their upload
`.svg` or `.html` would choose the type their file is served as, from
this application's origin, under the viewer's session.
"""

from __future__ import annotations

import pytest

from app.lib.file_object_utils import SAFE_TYPES, safe_suffix


@pytest.mark.parametrize(
    "filename", ["evil.svg", "evil.html", "evil.htm", "evil.xhtml", "evil.xml"]
)
def test_a_scriptable_extension_is_dropped(filename):
    assert safe_suffix(filename) == ""


@pytest.mark.parametrize("filename", ["photo.jpg", "photo.PNG", "doc.pdf", "t.ods"])
def test_an_expected_extension_survives(filename):
    assert safe_suffix(filename) == filename[filename.rindex(".") :].lower()


def test_an_unknown_extension_is_dropped_rather_than_guessed():
    assert safe_suffix("archive.tar.gz") == ""
    assert safe_suffix("noextension") == ""


@pytest.mark.parametrize(
    "bad", ["text/html", "image/svg+xml", "application/xhtml+xml", "text/xml"]
)
def test_no_allowed_extension_maps_to_an_executable_type(bad):
    assert bad not in SAFE_TYPES.values()
