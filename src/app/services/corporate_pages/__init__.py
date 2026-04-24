# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Corporate pages — minimal CMS for legal / marketing pages.

Source of truth for pages like CGV, politique de confidentialité,
mentions légales, « Notre offre », etc. Editable from the admin UI
instead of requiring a redeploy of the `static-pages/` files.

Spec: `local-notes/specs/corporate-pages-cms.md`.
"""

from __future__ import annotations

from ._models import CorporatePage, CorporatePageRepository
from ._service import CorporatePageService

__all__ = [
    "CorporatePage",
    "CorporatePageRepository",
    "CorporatePageService",
]
