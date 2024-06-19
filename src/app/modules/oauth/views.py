# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import redirect, url_for
from werkzeug.exceptions import NotFound

from app.flask.extensions import oauth

from . import blueprint


@blueprint.route("/<name>/login")
def login(name: str):
    client = oauth.create_client(name)
    if not client:
        raise NotFound

    redirect_uri = url_for(".authorize", name=name, _external=True)
    return client.authorize_redirect(redirect_uri)


@blueprint.route("/<name>/authorize")
def authorize(name: str):
    client = oauth.create_client(name)
    if not client:
        raise NotFound

    token = client.authorize_access_token()
    user = token.get("userinfo")
    if not user:
        user = client.userinfo()
        assert user

    # Sample answer
    # user: <UserInfo({
    #     'sub': '113216181535040193672',
    #     'name': 'Stefane Fermigier',
    #     'given_name': 'Stefane',
    #     'family_name': 'Fermigier',
    #     'picture': 'https://lh3.googleusercontent.com/...',
    #     'email': 'sfermigier@gmail.com',
    #     'email_verified': True,
    #     'locale': 'fr',
    # })> (UserInfo) len=8

    # if user:
    #     session['user'] = user

    # resp = oauth.google.get('account/verify_credentials.json')
    # debug(resp)
    # resp.raise_for_status()
    # profile = resp.json()
    # debug(profile)
    # do something with the token and profile
    return redirect("/")
