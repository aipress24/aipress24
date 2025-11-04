# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""POC Flask application for experimental features and prototypes.

This is a standalone Flask app that gets mounted into the main server.
It provides a playground for testing new features before integration.
"""

from __future__ import annotations

from flask import Flask, render_template

# Register blueprints
from poc.blueprints.bw_activation import bp as bw_activation_bp
from poc.blueprints.bw_activation_full import bp as bw_activation_full_bp
from poc.blueprints.rights_sales import bp as rights_sales_bp


def create_app() -> Flask:
    """Create and configure the POC Flask application.

    Returns:
        Flask: Configured POC application.
    """
    app = Flask(__name__)
    app.secret_key = "dev-secret-key-for-poc-only"  # noqa: S105

    app.register_blueprint(bw_activation_bp, url_prefix="/bw-activation")
    app.register_blueprint(bw_activation_full_bp, url_prefix="/bw-activation-full")
    app.register_blueprint(rights_sales_bp, url_prefix="/rights-sales")

    # Home page listing available POCs
    @app.route("/")
    def index():
        return render_template("poc_index.html")

    return app
