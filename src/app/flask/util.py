# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import importlib.metadata
from datetime import UTC, datetime
from pathlib import Path

from flask import current_app


def get_version() -> str:
    return importlib.metadata.version("aipress24-flask")


def get_home_path() -> Path:
    return (Path(current_app.root_path) / ".." / ".." / "..").resolve()


def utcnow() -> datetime:
    return datetime.now(UTC)
