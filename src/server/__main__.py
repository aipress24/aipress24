"""Server entry point module."""

# Copyright (c) 2024, Abilian SAS & TCA
from __future__ import annotations

import sys

from .main import serve

if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
        serve(port=port)
    else:
        serve()
