# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import warnings

from sqlalchemy.exc import SAWarning

from app.flask.main import create_app

warnings.simplefilter("ignore", DeprecationWarning)
warnings.simplefilter("ignore", UserWarning)
warnings.simplefilter("ignore", SAWarning)
warnings.simplefilter("ignore", FutureWarning)


app = create_app()
