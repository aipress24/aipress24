# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from pathlib import Path

from advanced_alchemy.types import FileObject
from flask.cli import with_appcontext
from flask_super.cli import command
from rich import print

from app.flask.extensions import db
from app.models.auth import User

OUTPUT_DIR = Path("orig_photos")


def upload_photos_core() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for png in OUTPUT_DIR.glob("*.png"):
        load_photo(png)


def load_photo(png: Path) -> None:
    print("loading", png)
    user_id = int(png.stem)
    content = png.read_bytes()
    user = db.session.get(User, user_id)
    if not user:
        print(f"User {user_id} not found, skipping")
        return

    image_file_object = FileObject(
        content=content,
        filename=f"{user_id}.png",
        content_type="image/png",
        backend="s3",
    )
    image_file_object.save()
    user.photo_image = image_file_object
    db.session.merge(user)
    db.session.commit()


@command(
    "upload-photos",
    short_help="Reads local photos, uploads to S3,",
)
@with_appcontext
def upload_photos_s3_cmd() -> None:
    upload_photos_core()
