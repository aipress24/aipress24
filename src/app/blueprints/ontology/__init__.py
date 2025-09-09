# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Blueprint

ontology_bp = Blueprint("ontology", __name__, template_folder="templates")


@ontology_bp.context_processor
def context_processor() -> dict:
    from flask import request, url_for

    breadcrumbs = [
        {"label": "Admin", "url": "/admin"},
        {"label": "Ontology", "url": url_for("ontology.list_entries")},
    ]

    # Add taxonomy name to breadcrumbs if present
    taxonomy_name = request.args.get("taxonomy_name")
    if taxonomy_name:
        breadcrumbs.append(
            {
                "label": taxonomy_name,
                "url": url_for("ontology.list_entries", taxonomy_name=taxonomy_name),
            }
        )

    return {
        "title": "Ontology Management",
        "breadcrumbs": breadcrumbs,
    }


from . import routes  # noqa: F401, E402

__all__ = ["ontology_bp"]
