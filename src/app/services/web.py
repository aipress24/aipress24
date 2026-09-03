"""Web service utilities for HTTP requests and responses."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import requests
from loguru import logger

#: A screenshot job waits behind this call; past that, the URL is
#: unusable for what it is wanted for anyway.
TIMEOUT = 15

_EMPTY_URLS = frozenset({"", "http://", "https://"})


def check_url(url: str) -> bool:
    """Does the URL answer 200, over HTTPS?

    An `http://` argument is rewritten: the caller (`jobs/screenshots`)
    only captures pages served in the clear by accident.
    """
    if url in _EMPTY_URLS:
        return False

    if url.startswith("http://"):
        logger.debug(f"check_url: rewriting {url!r} to https")
        url = url.replace("http://", "https://", 1)

    try:
        headers = {"User-Agent": "Python Requests"}
        result = requests.get(url, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        # The root of what `requests` raises — narrow enough that a bug
        # in this module surfaces instead of reading as "unreachable".
        logger.info(f"check_url: {url!r} unreachable ({e})")
        return False

    logger.debug(f"check_url: {url!r} answered {result.status_code}")
    return result.status_code == 200
