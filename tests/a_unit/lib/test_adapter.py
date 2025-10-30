# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for lib/adapter module."""

from __future__ import annotations

from app.lib.adapter import Adapter, adapt, unadapt


class TestAdapter:
    """Test suite for Adapter class."""

    def test_adapter_get_adaptee(self):
        """Test Adapter._get_adaptee method."""

        class MockAdaptee:
            id = 123

        class TestAdapter(Adapter):
            _adaptee_id = "_wrapped"

            def __init__(self, obj):
                self._wrapped = obj

        adaptee = MockAdaptee()
        adapter = TestAdapter(adaptee)

        assert adapter._get_adaptee() == adaptee
        assert adapter.id == 123


class TestAdapt:
    """Test suite for adapt function."""

    def test_adapt_already_correct_type(self):
        """Test adapt when object is already the correct type."""

        class MyClass:
            pass

        obj = MyClass()
        result = adapt(obj, MyClass)

        # Should return the same object without wrapping
        assert result is obj

    def test_adapt_different_type(self):
        """Test adapt when object needs to be wrapped."""

        class Source:
            value = 42

        class Target:
            def __init__(self, obj):
                self.wrapped = obj

        source = Source()
        result = adapt(source, Target)

        # Should be wrapped in Target class
        assert isinstance(result, Target)
        assert result.wrapped.value == 42


class TestUnadapt:
    """Test suite for unadapt function."""

    def test_unadapt_adapter(self):
        """Test unadapt with an Adapter object."""

        class MockAdaptee:
            id = 456

        class TestAdapter(Adapter):
            _adaptee_id = "_wrapped"

            def __init__(self, obj):
                self._wrapped = obj

        adaptee = MockAdaptee()
        adapter = TestAdapter(adaptee)

        result = unadapt(adapter)
        assert result is adaptee
        assert result.id == 456

    def test_unadapt_non_adapter(self):
        """Test unadapt with a non-Adapter object."""

        class RegularClass:
            value = 789

        obj = RegularClass()
        result = unadapt(obj)

        # Should return the same object
        assert result is obj
        assert result.value == 789
