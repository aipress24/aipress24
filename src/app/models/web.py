"""Web page and screenshot models for storing crawled content metadata."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WebPage(Base):
    """Model for storing web page metadata and status information."""

    __tablename__ = "web_page"

    url: Mapped[str] = mapped_column(primary_key=True)

    status: Mapped[int] = mapped_column(default=0)
    content_type: Mapped[str] = mapped_column(default="")
    lang: Mapped[str] = mapped_column(default="")

    screenshots: Mapped[list[ScreenShot]] = relationship(
        "ScreenShot", back_populates="page"
    )


class ScreenShot(Base):
    """Model for storing screenshot information linked to web pages."""

    __tablename__ = "web_screenshot"

    url: Mapped[str] = mapped_column(sa.ForeignKey("web_page.url"), primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    screenshot_id: Mapped[str] = mapped_column(default="")

    page: Mapped[WebPage] = relationship(WebPage, back_populates="screenshots")
