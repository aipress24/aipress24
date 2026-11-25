# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Wall posts: text, images, deletion, and the Messages tab of members."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import arrow
import fsspec
import pytest
import sqlalchemy as sa
from advanced_alchemy.types.file_object import storages
from advanced_alchemy.types.file_object.backends.fsspec import FSSpecBackend
from bs4 import BeautifulSoup, Tag
from flask import Flask
from flask.testing import FlaskClient
from PIL import Image
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from werkzeug.test import TestResponse

from app.enums import RoleEnum
from app.lib.base62 import base62
from app.models.auth import KYCProfile, Role, User
from app.models.short_post import ShortPost, ShortPostImage
from app.modules.swork.posts import MAX_IMAGES, PAGE_SIZE
from tests.c_e2e.conftest import make_authenticated_client

_counter = itertools.count()


@pytest.fixture
def role(db_session: Session) -> Role:
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()
    return role


def _make_user(db_session: Session, role: Role) -> User:
    number = next(_counter)
    user = User(
        email=f"wall-{number}@example.com",
        first_name="Jane",
        last_name=f"Doe{number}",
        active=True,
    )
    user.photo = b""
    user.roles.append(role)
    user.profile = KYCProfile(
        contact_type="PRESSE", profile_id="P001", profile_community="PRESS_MEDIA"
    )
    user.profile.show_contact_details = {}
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def author(db_session: Session, role: Role) -> User:
    return _make_user(db_session, role)


@pytest.fixture
def reader(db_session: Session, role: Role) -> User:
    """A member who does not follow the author."""
    return _make_user(db_session, role)


@pytest.fixture
def client(app: Flask, author: User) -> FlaskClient:
    return make_authenticated_client(app, author)


@pytest.fixture
def media_dir(tmp_path: Path) -> Iterator[Path]:
    """Store uploads in a temporary directory instead of S3."""
    original = storages.get_backend("s3")
    storages.register_backend(
        FSSpecBackend(fs=fsspec.filesystem("file"), key="s3", prefix=str(tmp_path))
    )
    yield tmp_path
    storages.register_backend(original)


def _png(color: str = "red") -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), color).save(buffer, "PNG")
    return buffer.getvalue()


def _add_post(db_session: Session, owner: User, text: str, **values) -> ShortPost:
    post = ShortPost(owner=owner, **values)
    post.text = text
    db_session.add(post)
    db_session.commit()
    return post


def _parse(response: TestResponse) -> BeautifulSoup:
    assert response.status_code == 200
    return BeautifulSoup(response.text, "html.parser")


def _find_post(page: BeautifulSoup, post: ShortPost) -> Tag:
    found = page.find(id=f"post-{post.id}")
    assert isinstance(found, Tag)
    return found


def _post_ids(page: BeautifulSoup) -> list[str]:
    return [str(item["id"]) for item in page.find_all("li", id=True)]


def _messages(client: FlaskClient, member: User, query: str = "") -> BeautifulSoup:
    response = client.get(
        f"/swork/members/{base62.encode(member.id)}?tab=messages{query}",
        headers={"HX-Request": "true"},
    )
    return _parse(response)


# --- text ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "R&D : 3 < 4 et https://x.test/?a=1&b=2",
        "<b>pas en gras</b> <script>alert(1)</script>",
        "ligne 1\n\nligne 2",
        "&amp; tel quel",
    ],
)
def test_a_text_is_shown_as_it_was_typed(
    client: FlaskClient, author: User, db_session: Session, text: str
) -> None:
    client.post("/swork/new_post", data={"message": text})
    post = db_session.scalars(sa.select(ShortPost)).one()
    assert post.text == text

    shown = _find_post(_parse(client.get("/swork/")), post)
    body = shown.find(class_="whitespace-pre-line")
    assert isinstance(body, Tag)
    assert body.text == text
    assert not body.find(["b", "script"])


def test_links_can_be_followed(
    client: FlaskClient, author: User, db_session: Session
) -> None:
    post = _add_post(db_session, author, "Voir https://x.test/?a=1&b=2.")
    shown = _find_post(_parse(client.get("/swork/")), post)
    link = shown.find("a", href="https://x.test/?a=1&b=2")
    assert isinstance(link, Tag)
    assert link["rel"] == ["noopener", "nofollow", "ugc"]


# --- date and origin -------------------------------------------------------


def test_an_imported_post_says_where_it_comes_from(
    client: FlaskClient, author: User, db_session: Session
) -> None:
    old = _add_post(
        db_session,
        author,
        "Ancien",
        published_at=arrow.get("2012-05-01T10:00:00Z"),
        external_ref="https://social.test/@me/1",
    )
    new = _add_post(db_session, author, "Nouveau")
    page = _parse(client.get("/swork/"))
    assert _post_ids(page) == [f"post-{new.id}", f"post-{old.id}"]
    shown = _find_post(page, old)
    assert "01 mai 2012 à 12:00" in shown.text
    link = shown.find("a", href="https://social.test/@me/1")
    assert isinstance(link, Tag)
    assert link.text == "social.test"
    assert "origine" not in _find_post(page, new).text


@pytest.mark.parametrize("reference", ["javascript:alert(1)", "doc-12", None])
def test_a_reference_is_only_a_link_if_it_is_one(
    client: FlaskClient, author: User, db_session: Session, reference: str | None
) -> None:
    post = _add_post(db_session, author, "x", external_ref=reference)
    shown = _find_post(_parse(client.get("/swork/")), post)
    assert "origine" not in shown.text
    assert "javascript" not in str(shown)


def test_a_post_without_publication_date_is_shown(
    client: FlaskClient, author: User, db_session: Session
) -> None:
    post = _add_post(db_session, author, "x", published_at=None)
    assert _find_post(_parse(client.get("/swork/")), post)


# --- images ----------------------------------------------------------------


def test_images_are_attached(
    client: FlaskClient, author: User, db_session: Session, media_dir: Path
) -> None:
    response = client.post(
        "/swork/new_post",
        data={
            "message": "",
            "images": [
                (BytesIO(_png("red")), "a.svg"),
                (BytesIO(_png("blue")), "b.png"),
            ],
        },
    )
    assert response.status_code == 302
    post = db_session.scalars(sa.select(ShortPost)).one()
    assert len(post.images) == 2
    shown = _find_post(_parse(client.get("/swork/")), post)
    urls = [str(image["src"]) for image in shown.select("a[target] > img")]
    assert urls == [image.url for image in post.images]
    # The stored type follows the bytes, not the name.
    assert all(url.startswith("/media/") and url.endswith(".png") for url in urls)


@pytest.mark.parametrize(
    "images",
    [
        [(b"<svg></svg>", "a.svg")],
        [(b"not an image", "a.png")],
        [(b"x" * 4 * 1024 * 1024, "big.png")],
        [(_png(), f"{n}.png") for n in range(MAX_IMAGES + 1)],
    ],
    ids=["svg", "text", "large", "many"],
)
def test_refused_images_create_nothing(
    client: FlaskClient, db_session: Session, media_dir: Path, images: list
) -> None:
    files = [(BytesIO(content), name) for content, name in images]
    response = client.post("/swork/new_post", data={"message": "x", "images": files})
    assert response.status_code == 302
    assert db_session.scalars(sa.select(ShortPost)).all() == []
    assert db_session.scalars(sa.select(ShortPostImage)).all() == []


# --- permalink and deletion ------------------------------------------------


def test_any_member_can_open_a_post(
    app: Flask, author: User, reader: User, db_session: Session
) -> None:
    post = _add_post(db_session, author, "Bonjour")
    url = f"/swork/posts/{base62.encode(post.id)}"
    client = make_authenticated_client(app, reader)
    shown = _find_post(_parse(client.get(url)), post)
    assert "Bonjour" in shown.text
    assert "Supprimer" not in shown.text


def test_a_visitor_cannot_open_a_post(
    app: Flask, author: User, db_session: Session
) -> None:
    post = _add_post(db_session, author, "Bonjour")
    response = app.test_client().get(f"/swork/posts/{post.id}")
    assert response.status_code in (302, 401)


def test_an_author_deletes_a_post(
    client: FlaskClient, author: User, db_session: Session
) -> None:
    post = _add_post(db_session, author, "Bonjour")
    shown = _find_post(_parse(client.get("/swork/")), post)
    button = shown.select_one("[hx-confirm]")
    assert isinstance(button, Tag)
    url = str(button["hx-post"])

    assert client.post(url).status_code == 200
    db_session.expire_all()
    assert post.deleted_at is not None
    assert _post_ids(_parse(client.get("/swork/"))) == []
    assert _post_ids(_messages(client, author)) == []
    # Nor can it be reached by its id.
    assert client.get(f"/swork/posts/{post.id}").status_code == 404
    assert client.get(f"/swork/{post.id}/alert_modal").status_code == 404
    assert client.post(url).status_code == 404


def test_no_one_else_deletes_a_post(
    app: Flask, author: User, reader: User, db_session: Session
) -> None:
    post = _add_post(db_session, author, "Bonjour")
    client = make_authenticated_client(app, reader)
    assert client.post(f"/swork/posts/{post.id}/delete").status_code == 404
    db_session.expire_all()
    assert post.deleted_at is None


def test_deleting_frees_the_reference(
    author: User, reader: User, db_session: Session
) -> None:
    first = _add_post(db_session, author, "x", external_ref="r")
    # Another member has their own references.
    _add_post(db_session, reader, "x", external_ref="r")
    with pytest.raises(IntegrityError):
        _add_post(db_session, author, "x", external_ref="r")
    db_session.rollback()
    first.deleted_at = arrow.utcnow()
    db_session.commit()
    _add_post(db_session, author, "x", external_ref="r")


# --- pages -----------------------------------------------------------------


def test_the_wall_has_pages(
    client: FlaskClient, author: User, db_session: Session
) -> None:
    start = arrow.get("2020-01-01")
    posts = [
        _add_post(db_session, author, f"n{n}", published_at=start.shift(days=n))
        for n in range(PAGE_SIZE + 1)
    ]
    expected = [f"post-{post.id}" for post in reversed(posts)]

    first = _parse(client.get("/swork/"))
    assert _post_ids(first) == expected[:PAGE_SIZE]
    assert first.find("a", string="Plus anciens")
    assert not first.find("a", string="Plus récents")
    second = _parse(client.get("/swork/?page=2"))
    assert _post_ids(second) == expected[PAGE_SIZE:]
    assert second.find("a", string="Plus récents")
    assert not second.find("a", string="Plus anciens")


@pytest.mark.parametrize("number", ["0", "-1", "x", str(10**30)])
def test_odd_page_numbers_are_survived(client: FlaskClient, number: str) -> None:
    assert client.get(f"/swork/?page={number}").status_code == 200


def test_members_see_all_the_messages_of_a_member(
    app: Flask, author: User, reader: User, db_session: Session
) -> None:
    # In Paris, this one is of 2013.
    late = _add_post(
        db_session, author, "a", published_at=arrow.get("2012-12-31T23:30:00Z")
    )
    recent = _add_post(
        db_session, author, "b", published_at=arrow.get("2015-06-01T10:00:00Z")
    )
    _add_post(db_session, reader, "c")
    client = make_authenticated_client(app, reader)

    page = _messages(client, author)
    assert _post_ids(page) == [f"post-{recent.id}", f"post-{late.id}"]
    assert "Messages (2)" in page.text
    years = page.find("nav", attrs={"aria-label": "Années"})
    assert isinstance(years, Tag)
    assert years.text.split() == ["Toutes", "2015", "2014", "2013"]

    assert _post_ids(_messages(client, author, "&year=2013")) == [f"post-{late.id}"]
    assert _post_ids(_messages(client, author, "&year=2014")) == []
    # A year which is not offered is ignored.
    for year in ("2012", "0", "99999999", "x"):
        assert len(_post_ids(_messages(client, author, f"&year={year}"))) == 2


def test_pages_keep_the_year(
    client: FlaskClient, author: User, db_session: Session
) -> None:
    for n in range(PAGE_SIZE + 1):
        moment = arrow.get("2013-03-01").shift(hours=n)
        _add_post(db_session, author, f"n{n}", published_at=moment)
    _add_post(db_session, author, "x", published_at=arrow.get("2014-03-01"))
    link = _messages(client, author, "&year=2013").find("a", string="Plus anciens")
    assert isinstance(link, Tag)
    assert link["hx-get"] == "?tab=messages&year=2013&page=2"


def test_a_member_without_message(client: FlaskClient, author: User) -> None:
    page = _messages(client, author)
    assert "Aucun message" in page.text
    assert "Messages (" not in page.text
