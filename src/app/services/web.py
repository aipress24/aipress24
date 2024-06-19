# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import requests
import rich

TIMEOUT = 60

scraper_is_installed = False


def check_url(url: str) -> bool:
    if url in {"", "http://", "https://"}:
        return False

    if url.startswith("http://"):
        url = url.replace("http://", "https://")

    try:
        headers = {"User-Agent": "Python Requests"}
        result = requests.get(url, headers=headers, timeout=TIMEOUT)
        status = result.status_code
        rich.print(f"[red]Status: {status}[/] for URL: {url}")
    except Exception as e:
        rich.print(f"[red]Status: {e}[/] for URL: {url}")
        status = -1

    return status == 200
