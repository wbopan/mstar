"""Tests for agent auto-discovery (agents/__init__.py).

Verifies that discover_agents(), get_agent_class(), and list_agents()
correctly find Agent subclasses in the agents/ package.
"""

import pytest

from agents import discover_agents, get_agent_class, list_agents
from agents.base import Agent
from agents.vanilla import VanillaAgent


class TestDiscoverAgents:
    """Test discover_agents() scanning."""

    def test_finds_vanilla_agent(self):
        """VanillaAgent should be discovered from agents/vanilla.py."""
        found = discover_agents()
        assert "VanillaAgent" in found

    def test_returns_agent_subclasses_only(self):
        """All discovered classes should be Agent subclasses."""
        found = discover_agents()
        for name, cls in found.items():
            assert issubclass(cls, Agent), f"{name} is not an Agent subclass"

    def test_does_not_include_base_agent(self):
        """The abstract Agent class itself should not appear in results."""
        found = discover_agents()
        assert "Agent" not in found

    def test_returns_dict(self):
        """discover_agents() returns a dict mapping str -> type."""
        found = discover_agents()
        assert isinstance(found, dict)
        for name, cls in found.items():
            assert isinstance(name, str)
            assert isinstance(cls, type)


class TestGetAgentClass:
    """Test get_agent_class() lookup."""

    def test_get_vanilla_agent(self):
        """Should return VanillaAgent class by name."""
        cls = get_agent_class("VanillaAgent")
        assert cls is VanillaAgent

    def test_unknown_agent_raises(self):
        """Should raise ValueError for unknown agent name."""
        with pytest.raises(ValueError, match="not found"):
            get_agent_class("NonExistentAgent")

    def test_error_message_lists_available(self):
        """Error message should list available agent names."""
        with pytest.raises(ValueError, match="VanillaAgent"):
            get_agent_class("FakeAgent")


class TestListAgents:
    """Test list_agents() listing."""

    def test_returns_sorted_list(self):
        """Should return a sorted list of agent class names."""
        names = list_agents()
        assert isinstance(names, list)
        assert names == sorted(names)

    def test_includes_vanilla(self):
        """VanillaAgent should be in the list."""
        assert "VanillaAgent" in list_agents()
