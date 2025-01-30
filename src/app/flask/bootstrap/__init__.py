# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .ontologies import import_taxonomies
from .zip_codes import import_countries, import_zip_codes

__all__ = ["import_countries", "import_taxonomies", "import_zip_codes"]
