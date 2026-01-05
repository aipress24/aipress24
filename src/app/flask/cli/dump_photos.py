# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from pathlib import Path

from flask import current_app
from flask.cli import with_appcontext
from flask_super.cli import command  # Assumed import based on user's example
from sqlalchemy import Column, Integer, LargeBinary, String, create_engine, select
from sqlalchemy.orm import Session, declarative_base

OUTPUT_DIR = Path("orig_photos")
TABLE_NAME = "aut_user"


Base = declarative_base()


class UserMigrationModel(Base):
    __tablename__ = TABLE_NAME
    id = Column(Integer, primary_key=True)
    photo = Column(LargeBinary)
    photo_filename = Column(String)


def dump_photos_core(db_uri: str) -> None:
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


@command(
    "dump-photos",
    short_help="Extracts old data photo binary.",
)
@with_appcontext
def dump_photos_cmd() -> None:
    app = current_app
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    if not db_uri:
        print("Error: SQLALCHEMY_DATABASE_URI not configured")
        return
    dump_photos_core(db_uri)
