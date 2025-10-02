# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from flask import request
from flask_login import current_user
from werkzeug.exceptions import Forbidden, Unauthorized

from app.services.roles import has_role

if TYPE_CHECKING:
    from app.models import User


@dataclass(frozen=True)
class Rule:
    """A security rule that maps a URL prefix to a validation function."""

    prefix: str
    is_allowed: Callable[[User], bool]


class Doorman:
    """A class to manage and enforce path-based security rules."""

    def __init__(self) -> None:
        self.rules: list[Rule] = []

    def add_rule(self, rule: Rule) -> None:
        """Adds a new security rule to the list."""
        self.rules.append(rule)

    def check_access(self) -> None:
        """
        Checks the incoming request against all registered rules.

        Raises:
            Unauthorized (401): If the path is protected and the user is not logged in.
            Forbidden (403): If the user is logged in but does not have the required permissions.
        """
        for rule in self.rules:
            if not request.path.startswith(rule.prefix):
                continue

            if not current_user.is_authenticated:
                # The user is not logged in, but the path requires a permission check.
                # The correct response is 401 Unauthorized.
                msg = "Authentication is required to access this resource."
                raise Unauthorized(msg)

            user = cast("User", current_user)

            if not rule.is_allowed(user):
                # The user is logged in but lacks permission.
                # The correct response is 403 Forbidden.
                msg = "You do not have the necessary permissions for this resource."
                raise Forbidden(msg)

            return

    def rule(self, prefix: str) -> Callable:
        """A decorator to register a function as a security rule for a URL prefix."""

        def decorator(func: Callable[[User], bool]) -> Callable[[User], bool]:
            # Create the rule object using the NamedTuple
            rule = Rule(prefix=prefix, is_allowed=func)
            self.add_rule(rule)
            return func

        return decorator


# Singleton instance of Doorman
doorman = Doorman()


@doorman.rule(prefix="/admin/")
def check_admin(user: User) -> bool:
    """Rule: Only users with the 'ADMIN' role can access /admin/ paths."""
    return has_role(user, "ADMIN")
