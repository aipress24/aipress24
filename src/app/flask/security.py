# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import Flask
from loguru import logger

from app.flask.extensions import oauth


def register_oauth_providers(app: Flask) -> None:
    logger.info("Registering OAuth providers")
    register_google()
    register_gitlab()
    # register_linuxfr()
    register_github()


def register_google() -> None:
    conf_url = "https://accounts.google.com/.well-known/openid-configuration"
    oauth.register(
        name="google",
        server_metadata_url=conf_url,
        client_kwargs={"scope": "openid email profile"},
    )


def register_gitlab() -> None:
    """Support Gitlab.

    * Dashboard: https://gitlab.com/oauth/applications/
    * Docs: https://docs.gitlab.com/ce/api/oauth2.html
    * API reference: https://docs.gitlab.com/ee/api/README.html
    """
    # authorization_endpoint: "https://gitlab.com/oauth/authorize",
    # token_endpoint: "https://gitlab.com/oauth/token",

    # access_token_url = 'https://gitlab.com/oauth/token'
    # authorize_url = 'https://gitlab.com/oauth/authorize'
    # base_url = 'https://gitlab.com/api/v4'
    # name = 'gitlab'
    # user_info_url = 'https://gitlab.com/api/v4/user'

    conf_url = "https://gitlab.com/.well-known/openid-configuration"
    oauth.register(
        name="gitlab",
        server_metadata_url=conf_url,
        client_kwargs={"scope": "openid email profile"},
    )
    # Typical answer:
    # user: <UserInfo({
    #     'sub': '523040',
    #     'sub_legacy': '8f071d5aa5290fc8891cca3b13431b25a01f2df6ce9b57f0fb7ed6d2d23cd5eb',
    #     'name': 'Stefane Fermigier',
    #     'nickname': 'sfermigier',
    #     'email': 'sf@fermigier.com',
    #     'email_verified': True,
    #     'profile': 'https://gitlab.com/sfermigier',
    #     'picture': '...',
    #     'groups': [
    #         'abilian',
    #         'gaia-x/gaia-x-community',
    #         'gaia-x/gaia-x-community/mvg-demonstrator',
    #         'gaia-x/gaia-x-community/gxa_review',
    #         'gaia-x/gaia-x-community/dataspace-finance-insurance',
    #         'gaia-x/gaia-x-community/dataspace-finance-insurance/faic-financial-ai-cluster',
    #         'gaia-x/gaia-x-community/gx-hackathon',
    #         'gaia-x/gaia-x-community/gaia-x-catalogue',
    #     ],
    # })> (UserInfo) len=9


def register_github() -> None:
    oauth.register(
        name="github",
        # api_base_url='https://linuxfr.org/api/v1/',
        authorize_url="https://github.com/login/oauth/authorize",
        # request_token_url='https://linuxfr.org/api/oauth/token',
        # access_token_url='https://api.twitter.com/oauth/access_token',
        # userinfo_endpoint="https://linuxfr.org/api/v1/me",
        # userinfo_endpoint='account/verify_credentials.json?include_email=true&skip_status=true',
        # userinfo_compliance_fix=normalize_twitter_userinfo,
        # fetch_token=lambda: session.get('token'),  # DON'T DO IT IN PRODUCTION
        # client_kwargs={
        #     'scope': 'account'
        # }
    )

    # https://github.com/login/oauth/authorize


# def register_linuxfr() -> None:
#     oauth.register(
#         name="linuxfr",
#         api_base_url="https://linuxfr.org/api/v1/",
#         authorize_url="https://linuxfr.org/api/oauth/authorize",
#         request_token_url="https://linuxfr.org/api/oauth/token",
#         # access_token_url='https://api.twitter.com/oauth/access_token',
#         # userinfo_endpoint="https://linuxfr.org/api/v1/me",
#         # userinfo_endpoint='account/verify_credentials.json?include_email=true&skip_status=true',
#         # userinfo_compliance_fix=normalize_twitter_userinfo,
#         # fetch_token=lambda: session.get('token'),  # DON'T DO IT IN PRODUCTION
#         client_kwargs={"scope": "account"},
#     )
