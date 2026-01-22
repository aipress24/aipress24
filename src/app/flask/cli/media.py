"""CLI commands for media/photo operations."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from pathlib import Path

from advanced_alchemy.types import FileObject
from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import group
from rich import print
from sqlalchemy import Column, Integer, LargeBinary, String, create_engine, select
from sqlalchemy.orm import Session, declarative_base

from app.flask.extensions import db
from app.models.auth import User

OUTPUT_DIR = Path("orig_photos")
TABLE_NAME = "aut_user"

Base = declarative_base()


class UserMigrationModel(Base):
    __tablename__ = TABLE_NAME
    id = Column(Integer, primary_key=True)
    photo = Column(LargeBinary)
    photo_filename = Column(String)


@group(short_help="Media/photo operations")
def media() -> None:
    """Commands for photo import/export operations."""


@media.command("dump-photos", short_help="Extract photos from old database")
@with_appcontext
def dump_photos_cmd() -> None:
    app = current_app
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if not db_uri:
        print("Error: SQLALCHEMY_DATABASE_URI not configured")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    engine = create_engine(db_uri)

    with Session(engine) as session:
        users_with_photos = session.scalars(
            select(UserMigrationModel).where(UserMigrationModel.photo.is_not(None))
        ).all()

        for user in users_with_photos:
            user_id = user.id
            photo_data: bytes = user.photo  # type: ignore[assignment]
            output_path = OUTPUT_DIR / f"{user_id}.png"
            output_path.write_bytes(photo_data)


@media.command("upload-photos", short_help="Upload local photos to S3")
@with_appcontext
def upload_photos_cmd() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for png in OUTPUT_DIR.glob("*.png"):
        _load_photo(png)


def _load_photo(png: Path) -> None:
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
