# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/lib/controllers.py."""

from __future__ import annotations

import pytest

from app.flask.lib.controllers import Dispatcher, controller, get, post, route


class TestDecorators:
    """Test controller decorators."""

    def test_get_decorator_sets_meta(self):
        """@get decorator should set _meta with GET method."""

        @get("/test")
        def handler():
            pass

        assert hasattr(handler, "_meta")
        assert handler._meta["path"] == "/test"
        assert handler._meta["methods"] == ["GET"]

    def test_post_decorator_sets_meta(self):
        """@post decorator should set _meta with POST method."""

        @post("/submit")
        def handler():
            pass

        assert hasattr(handler, "_meta")
        assert handler._meta["path"] == "/submit"
        assert handler._meta["methods"] == ["POST"]

    def test_route_decorator_sets_meta(self):
        """@route decorator should set _meta with custom methods."""

        @route("/resource", methods=["GET", "POST", "PUT"])
        def handler():
            pass

        assert hasattr(handler, "_meta")
        assert handler._meta["path"] == "/resource"
        assert handler._meta["methods"] == ["GET", "POST", "PUT"]

    def test_get_requires_leading_slash(self):
        """@get should assert path starts with /."""
        with pytest.raises(AssertionError):

            @get("no-slash")
            def handler():
                pass

    def test_post_requires_leading_slash(self):
        """@post should assert path starts with /."""
        with pytest.raises(AssertionError):

            @post("no-slash")
            def handler():
                pass

    def test_route_requires_leading_slash(self):
        """@route should assert path starts with /."""
        with pytest.raises(AssertionError):

            @route("no-slash", methods=["GET"])
            def handler():
                pass


class TestDispatcher:
    """Test Dispatcher class."""

    def test_dispatcher_calls_method(self):
        """Dispatcher should instantiate class and call method."""

        class TestController:
            def action(self, arg):
                return f"result: {arg}"

        dispatcher = Dispatcher(TestController, "action")
        result = dispatcher("hello")
        assert result == "result: hello"

    def test_dispatcher_has_name(self):
        """Dispatcher should have __name__ attribute."""

        class TestController:
            def action(self):
                pass

        dispatcher = Dispatcher(TestController, "action")
        assert dispatcher.__name__ == "Dispatcher"


class TestControllerDecorator:
    """Test @controller decorator."""

    def test_controller_adds_meta(self):
        """@controller should add meta attribute to class."""

        @controller
        class MyController:
            pass

        assert hasattr(MyController, "meta")
