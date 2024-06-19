# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.models.orgs import OrganisationType
from app.ui.labels import make_label


class A:
    class Meta:
        type_label = "A"


def test_labels() -> None:
    assert make_label(OrganisationType.AUTO) == "Non-officialisée"
    assert make_label("foo") == "???"
    assert make_label(A()) == "A"
