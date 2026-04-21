# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dramatiq actor: justificatif PDF generation after a paid purchase."""

from __future__ import annotations

from app.dramatiq.job import job


@job()
def generate_justificatif(purchase_id: int) -> None:
    """Generate the PDF for a paid JUSTIFICATIF purchase."""
    from app.modules.wire.services.justificatif import (
        generate_justificatif_pdf,
    )

    generate_justificatif_pdf(purchase_id)
