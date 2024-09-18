#!/usr/bin/env python3

# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only


from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

__all__ = ["build_npm_assets"]

logger = logging.getLogger()

PROJECT_ROOT = Path(__file__).parent.parent
NODEENV = "nodeenv"
DEFAULT_VENV_PATH = Path(PROJECT_ROOT / ".venv")


def run(cmd, **kwargs):
    # print([str(arg) for arg in cmd])
    subprocess.run(cmd, **kwargs)


@contextlib.contextmanager
def chdir(path: str | Path):
    origin = Path().absolute()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(origin)


def build_npm_assets(setup_kwargs: Any) -> Any:
    found_in_local_venv = Path(DEFAULT_VENV_PATH / "bin" / NODEENV).exists()
    nodeenv_command = (
        f"{DEFAULT_VENV_PATH}/bin/{NODEENV}" if found_in_local_venv else NODEENV
    )
    install_dir = (
        DEFAULT_VENV_PATH
        if found_in_local_venv
        else os.environ.get("VIRTUAL_ENV", sys.prefix)
    )

    logger.info("Installing Node environment to %s:", install_dir)
    run(
        [nodeenv_command, "--force", install_dir],
        check=True,
    )  # noqa: S603, PLW1510

    with chdir("vite"):
        logger.info("Installing dependencies:")
        run(["npm", "install"])  # noqa: S607, B607, S603, PLW1510

        logger.info("Building NPM assets:")
        run(["npm", "run", "build"])  # noqa: S607, B607, S603, PLW1510

    return setup_kwargs


if __name__ == "__main__":
    build_npm_assets({})
