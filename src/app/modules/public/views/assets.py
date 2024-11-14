# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from flask import send_from_directory

from .. import blueprint


@blueprint.route("/cdn/<path:filename>")
def get_asset(filename):
    assets_dir = str(Path.cwd() / "cdn" / "dist")
    return send_from_directory(assets_dir, filename)


# @blueprint.route("/src/assets/<path:filename>")
# def get_src_asset(filename):
#     assets_dir = str(Path(os.getcwd()) / "front" / "src" / "assets")
#     return send_from_directory(assets_dir, filename)
