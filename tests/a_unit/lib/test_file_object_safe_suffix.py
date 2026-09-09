# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The stored extension decides what `/media` serves — audit finding 2.

`create_file_object` used the uploader's own suffix verbatim, and
`/media/<name>` derives the Content-Type from it with
`mimetypes.guess_type`. A member who named their upload `.svg` or
`.html` therefore chose the type their file would be served as, from
this application's origin, under the viewer's session.
"""

from __future__ import annotations

import mimetypes

import pytest

from app.lib.file_object_utils import SAFE_SUFFIXES, safe_suffix
from app.modules.media.views import SERVABLE_TYPES


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


def test_no_allowed_extension_maps_to_an_executable_type():
    """The two lists have to agree: an extension we keep must map to a
    type `/media` is willing to name, and none of those may be one a
    browser executes."""
    for suffix in SAFE_SUFFIXES:
        guessed, _ = mimetypes.guess_type(f"{'a' * 64}{suffix}")
        assert guessed in SERVABLE_TYPES, f"{suffix} -> {guessed}"


@pytest.mark.parametrize(
    "bad", ["text/html", "image/svg+xml", "application/xhtml+xml", "text/xml"]
)
def test_media_refuses_to_name_an_executable_type(bad):
    assert bad not in SERVABLE_TYPES
