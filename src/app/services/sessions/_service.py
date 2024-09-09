# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import define
from flask import session as flask_session
from flask_super.decorators import service
from sqlalchemy.orm import scoped_session
from svcs import Container
from svcs.flask import container

from app.services.auth import AuthService

from ._models import Session, SessionRepository

_marker = object()


@service
@define
class SessionService:
    auth_service: AuthService
    db_session: scoped_session
    # repo: SessionRepository

    @classmethod
    def svcs_factory(cls, ctn: Container) -> SessionService:
        return cls(
            auth_service=ctn.get(AuthService),
            db_session=ctn.get(scoped_session),
            # repo=ctn.get(SessionRepository),
        )

    def get_session(self) -> Session | None:
        """Get the user's session."""
        repo = container.get(SessionRepository)
        user = self.auth_service.get_user()
        if user.is_authenticated:
            return repo.get_one_or_none(user_id=user.id)

        # Else, use session_id, if any
        session_id = flask_session.get("session_id", "")
        if not session_id:
            return None
        return repo.get_one_or_none(session_id=session_id)

    def __contains__(self, item) -> bool:
        """Check if a key exists in the user's session."""
        session = self.get_session()
        if not session:
            return False

        return item in session

    def get(self, key, default=_marker):
        """Get a value from the user's session by key."""
        session = self.get_session()
        if not session:
            if default is _marker:
                raise KeyError(key)
            return default

        return session.get(key, default)

    def __getitem__(self, item):
        """Get a value from the user's session by key."""
        return self.get(item)

    def set(self, key, value):
        """Set a value in the user's session by key."""
        user = self.auth_service.get_user()
        repo = container.get(SessionRepository)
        if user.is_authenticated:
            session, _created = repo.get_or_upsert(user_id=user.id)
            session.set(key, value)
            repo.add(session, auto_commit=True)
            return
        session_id = flask_session.get("session_id", "")
        if not session_id:
            return
        session, _created = repo.get_or_upsert(session_id=session_id)
        session.set(key, value)
        repo.add(session, auto_commit=True)

    def __setitem__(self, key, value):
        """Set a value in the user's session by key."""
        return self.set(key, value)
