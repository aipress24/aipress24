"""Application-wide constants and limits."""

# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

MAX_IMAGE_SIZE = 4 * 1024 * 1024
MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
MAX_GALLERY_IMAGES = 10
STRIPE_RESPONSE_ALWAYS_200 = 1
MAX_CONTENT_LENGTH = 32 * 1024 * 1024
# Werkzeug 3+ default is 500 KB, which trips the cropper.js
# base64 data-URL flow : a 1 MB image → ~1.4 MB data-URL form field
# → 413. Bump to 12 MB so any image up to MAX_IMAGE_SIZE (4 MB)
# survives base64 encoding (4 × 4/3 ≈ 5.3 MB) with headroom for
# other form fields. Cf. bugs/resolus/0106.
MAX_FORM_MEMORY_SIZE = 12 * 1024 * 1024
