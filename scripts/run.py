#!/usr/bin/env python3

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import logging
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger()

PROJECT_ROOT = Path(__file__).parent.parent
NODEENV = "nodeenv"

VENV_PATH = Path(shutil.which("flask")).parent.parent

PORT = os.environ.get("PORT", 5000)


def sh(cmd: list | str):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    print(f"Running: {cmd}")
    subprocess.run(cmd, check=True)


def install_npm():
    if (VENV_PATH / "bin" / "npm").exists():
        return

    found_in_local_venv = (VENV_PATH / "bin" / NODEENV).exists()
    if found_in_local_venv:
        logger.info("`nodeenv` command found in local venv.")
        install_dir = VENV_PATH
        nodeenv_command = f"{install_dir}/bin/{NODEENV}"
    else:
        logger.info("`nodeenv` command not found in local venv.")
        install_dir = Path(os.environ.get("VIRTUAL_ENV", sys.prefix))
        nodeenv_command = NODEENV

    if not (install_dir / "bin" / "npm").exists():
        logger.info("Installing Node environment to %s:", install_dir)
        sh([nodeenv_command, "--force", install_dir])


install_npm()

sh("flask vite install")
sh("flask vite build")
