# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from devtools import debug
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from splinter import Browser
from splinter.driver.flaskclient import FlaskClient

from .utils import create_stuff, login


@pytest.fixture
def browser(app, db: SQLAlchemy) -> Browser:
    create_stuff(db)
    browser = Browser("flask", app=app)
    login(browser)
    return browser


@pytest.mark.skip(reason="Not working")
def test_home(app: Flask, browser: FlaskClient) -> None:
    browser.visit("/")
    assert browser.status_code.code == 200


@pytest.mark.skip(reason="Not working")
def test_backdoor(app: Flask, browser: FlaskClient) -> None:
    browser.visit("/backdoor/")
    debug(browser, vars(browser))
    assert browser.status_code.code == 200

    # browser.visit("/backdoor/1")
    # assert browser.status_code.code == 200


@pytest.mark.skip(reason="Not working")
def test_wip(app: Flask, browser: FlaskClient) -> None:
    browser.visit("/backdoor/0")
    browser.visit("/wip")
    assert browser.status_code.code == 200
    assert browser.is_text_present("WIP")

    browser.visit("/wip/contents?mode=list")
