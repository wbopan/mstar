"""Tests for BaseEnvironment contract (state_bench/environment.py).

Verifies that:
- Subclasses must implement tool_handlers and get_full_snapshot
- parse_bool utility works correctly
- Constructor sets self.now
"""

import pytest

from state_bench.environment import BaseEnvironment


class TestBaseEnvironmentContract:
    """Test that BaseEnvironment enforces the abstract interface."""

    def test_cannot_instantiate_directly(self):
        """BaseEnvironment is abstract and cannot be instantiated."""
        with pytest.raises(TypeError, match="abstract method"):
            BaseEnvironment(env_data=None, now="2026-06-15")

    def test_subclass_missing_tool_handlers_raises(self):
        """Subclass without tool_handlers cannot be instantiated."""

        class IncompleteEnv(BaseEnvironment):
            def get_full_snapshot(self):
                return {}

        with pytest.raises(TypeError, match="abstract method"):
            IncompleteEnv(env_data=None, now="2026-06-15")

    def test_subclass_missing_snapshot_raises(self):
        """Subclass without get_full_snapshot cannot be instantiated."""

        class IncompleteEnv(BaseEnvironment):
            @property
            def tool_handlers(self):
                return {}

        with pytest.raises(TypeError, match="abstract method"):
            IncompleteEnv(env_data=None, now="2026-06-15")

    def test_complete_subclass_works(self):
        """Subclass implementing both abstract members can be instantiated."""

        class ValidEnv(BaseEnvironment):
            @property
            def tool_handlers(self):
                return {"my_tool": lambda x: x}

            def get_full_snapshot(self):
                return {"entities": {}}

        env = ValidEnv(env_data=None, now="2026-06-15")
        assert env.now == "2026-06-15"
        assert "my_tool" in env.tool_handlers
        assert env.get_full_snapshot() == {"entities": {}}


class TestBaseEnvironmentInit:
    """Test constructor behavior."""

    def test_sets_now(self):
        """Constructor should set self.now."""

        class MinimalEnv(BaseEnvironment):
            @property
            def tool_handlers(self):
                return {}

            def get_full_snapshot(self):
                return {}

        env = MinimalEnv(env_data="some_data", now="2026-01-01T00:00:00")
        assert env.now == "2026-01-01T00:00:00"


class TestParseBool:
    """Test the parse_bool static method."""

    def test_none_returns_none(self):
        assert BaseEnvironment.parse_bool(None) is None

    def test_bool_true(self):
        assert BaseEnvironment.parse_bool(True) is True

    def test_bool_false(self):
        assert BaseEnvironment.parse_bool(False) is False

    def test_string_true_variants(self):
        assert BaseEnvironment.parse_bool("true") is True
        assert BaseEnvironment.parse_bool("True") is True
        assert BaseEnvironment.parse_bool("TRUE") is True
        assert BaseEnvironment.parse_bool("1") is True
        assert BaseEnvironment.parse_bool("yes") is True
        assert BaseEnvironment.parse_bool("Yes") is True

    def test_string_false_variants(self):
        assert BaseEnvironment.parse_bool("false") is False
        assert BaseEnvironment.parse_bool("False") is False
        assert BaseEnvironment.parse_bool("0") is False
        assert BaseEnvironment.parse_bool("no") is False
        assert BaseEnvironment.parse_bool("") is False

    def test_int_values(self):
        assert BaseEnvironment.parse_bool(1) is True
        assert BaseEnvironment.parse_bool(0) is False

    def test_callable_from_instance(self):
        """parse_bool should be callable as instance method too."""

        class MinimalEnv(BaseEnvironment):
            @property
            def tool_handlers(self):
                return {}

            def get_full_snapshot(self):
                return {}

        env = MinimalEnv(env_data=None, now="now")
        assert env.parse_bool("true") is True
        assert env.parse_bool(None) is None
