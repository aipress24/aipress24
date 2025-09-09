# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from flask import Flask


def create_app():
    app = Flask(__name__)
    # ... other app configurations ...

    # Register the ontology blueprint
    from app.blueprints.ontology import ontology_bp

    app.register_blueprint(ontology_bp)

    return app
