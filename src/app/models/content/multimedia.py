# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
'-----------------------------------------------------------------
'Multimedia & Composite (editorial) content
'-----------------------------------------------------------------

abstract class MultimedialContent {
    +format: string
    +description: string
    +file_size: integer
}
MultimedialContent -up-|> EditorialContent

abstract class VisualContent {
    +height: integer
    +width: integer
    +resolution: string
}
VisualContent -up-|> MultimedialContent

class Image {
}
Image -up-|> VisualContent

class Photo {
    +exif_metadata: dict
}
Photo -up-|> Image

class Illustration {
}
Illustration -up-|> Image

class Dataviz {
}
Dataviz -up-|> Image

class Video {
    +duration: integer
    +encoding: string
    +transcript: string
}
Video -up-|> VisualContent

class Audio {
    +duration: integer
    +encoding: string
    +transcript: string
}
Audio -up-|> MultimedialContent

class Composite {
    +TODO
}
Composite -up-|> MultimedialContent

class ReportagePhoto {
}
ReportagePhoto -up-|> Composite

"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import EditorialContent


# Abstract
class MultimedialContent(EditorialContent):
    __tablename__ = "edt_multimedia"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(EditorialContent.id), primary_key=True
    )

    format: Mapped[str] = mapped_column(default="")
    description: Mapped[str] = mapped_column(default="")
    blob: Mapped[bytes | None]
    file_size: Mapped[int] = mapped_column(default=0)


# Abstract
class VisualContent(MultimedialContent):
    __tablename__ = "edt_visual"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(MultimedialContent.id), primary_key=True
    )

    height: Mapped[int] = mapped_column(default=0)
    width: Mapped[int] = mapped_column(default=0)
    resolution: Mapped[str] = mapped_column(default="")


class Image(VisualContent):
    __tablename__ = "edt_image"

    id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey(VisualContent.id), primary_key=True
    )
    subtype: Mapped[str] = mapped_column(default="photo")
