# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# from __future__ import annotations
#
# from . import blueprint
#
#
# @blueprint.route("/", methods=["GET", "POST"])
# @blueprint.route("/<path:path>", methods=["GET", "POST"])
# def dashboard(path=""):
#     # environ = request.environ.copy()
#
#     dashboard_app = create_dramatiq_app()
#
#     def wrapped_app(environ, start_response):
#         environ["SCRIPT_NAME"] = "/queue"
#         environ["PATH_INFO"] = "/" + path
#         return dashboard_app(environ, start_response)
#
#     return wrapped_app
#
#
# def create_dramatiq_app():
#     import dramatiq
#     from dramatiq_dashboard import DashboardApp
#
#     broker = dramatiq.get_broker()
#     return DashboardApp(broker, prefix="/queue")
