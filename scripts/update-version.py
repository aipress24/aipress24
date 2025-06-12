#!/usr/bin/env python3

import time
from pathlib import Path

import tomlkit

pyproject = tomlkit.load(Path("pyproject.toml").open())

current_version = pyproject["project"]["version"]
today = time.strftime("%Y.%m.%d")

if current_version.startswith(today):
    serial = int(current_version.split(".")[-1][0])
    version = f"{today}.{serial + 1}"
else:
    version = f"{today}.1"

print(f"Updating version: {version}")

pyproject["project"]["version"] = version

tomlkit.dump(pyproject, Path("pyproject.toml").open("w"))
