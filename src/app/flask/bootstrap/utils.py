# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only


from __future__ import annotations

import os

import psutil

g = {"max_rss": 0}


def show_memory_usage() -> None:
    process = psutil.Process(os.getpid())
    memory_info = process.memory_info()
    print(f"RSS: {memory_info.rss / (1024 * 1024):.2f} MB")  # Convert to MB

    g["max_rss"] = max(g["max_rss"], memory_info.rss)
    print(f"Max RSS: {g['max_rss'] / (1024 * 1024):.2f} MB")  # Convert to MB
