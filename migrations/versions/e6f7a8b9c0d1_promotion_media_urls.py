"""rewrite the signed S3 URLs frozen in promotion bodies

The « AiPRESS24 vous informe » boxes are stored HTML, edited with Trix.
Trix uploads used to return a *signed, absolute* S3 URL, which the
editor wrote into the body verbatim. A signed URL carries a signature
tied to a key and an algorithm, so it stops validating the day either
changes — which is what happened, and the four boxes started serving
`SignatureDoesNotMatch` instead of their image.

Uploads have returned `/media/<sha256>` since the `media_url()` wrapper
landed; this rewrites what was written before. The files themselves were
never lost: all four were read back from the bucket before this was
written.

Only the query string and the host go; the storage name in the path is
what `/media/` serves, and the backend prefix (`<bucket>/files`) is what
makes the two line up.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-09-18 12:05:00.000000

"""

import re

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None

# An absolute URL whose path ends in a content-addressed storage name,
# carrying a v2 or v4 signature. The name is the only part worth keeping.
_SIGNED_URL = re.compile(
    r"https?://[^\"'\s]+?/([0-9a-f]{64}(?:\.[A-Za-z0-9]{1,10})?)"
    r"\?[^\"'\s]*(?:AWSAccessKeyId|X-Amz-Signature)[^\"'\s]*"
)

promotion = sa.table("adm_promotion", sa.column("slug"), sa.column("body", sa.Text))


def upgrade():
    bind = op.get_bind()
    rewritten = 0
    for slug, body in bind.execute(sa.select(promotion.c.slug, promotion.c.body)):
        if not body:
            continue
        new_body, count = _SIGNED_URL.subn(r"/media/\1", body)
        if not count:
            continue
        bind.execute(
            promotion.update().where(promotion.c.slug == slug).values(body=new_body)
        )
        rewritten += count
    print(f"rewrote {rewritten} signed URL(s) in promotion bodies")


def downgrade():
    """Nothing to undo: the old URLs did not resolve, which is why they
    were replaced."""
