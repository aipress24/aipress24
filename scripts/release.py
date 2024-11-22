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
from pathlib import Path

logger = logging.getLogger()


def sh(cmd: list | str):
    if isinstance(cmd, str):
        cmd = shlex.split(cmd)
    print(f"Running: {cmd}")
    subprocess.run(cmd, check=True)


def install_npm():
    venv_path = Path(shutil.which("flask")).parent.parent

    if (venv_path / "bin" / "npm").exists():
        return

    logger.info("Installing Node environment to %s:", venv_path)
    sh(["nodeenv", "--force", venv_path])


def main():
    print("Environment variables:")
    for k in sorted(os.environ):
        print(f"{k}={os.environ[k]}")
    print()

    print("Installing npm")
    install_npm()
    print()

    print("Creating assets")
    sh("flask vite install")
    sh("flask vite build")
    print()

    print("Migrating database")
    sh("flask db upgrade")
    print()


main()
