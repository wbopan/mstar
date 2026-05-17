"""Tests for DictMixin serialization (state_bench/schemas.py).

Verifies that DictMixin provides correct to_dict/from_dict for flat
dataclasses, handles round-trips, and ignores unknown fields.
"""

from dataclasses import dataclass, field
from typing import Any

from state_bench.schemas import DictMixin


@dataclass
class SimpleRecord(DictMixin):
    """Test dataclass with basic types."""

    name: str
    value: int
    active: bool = True


@dataclass
class RecordWithDefaults(DictMixin):
    """Test dataclass with complex defaults."""

    record_id: str
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    optional_field: str | None = None


class TestDictMixinToDict:
    """Test to_dict() serialization."""

    def test_basic_to_dict(self):
        """All fields should appear in the output dict."""
        record = SimpleRecord(name="test", value=42, active=True)
        result = record.to_dict()
        assert result == {"name": "test", "value": 42, "active": True}

    def test_to_dict_with_defaults(self):
        """Default values should be included in output."""
        record = RecordWithDefaults(record_id="R-1")
        result = record.to_dict()
        assert result["record_id"] == "R-1"
        assert result["tags"] == []
        assert result["metadata"] == {}
        assert result["optional_field"] is None

    def test_to_dict_with_populated_fields(self):
        """Populated fields should serialize correctly."""
        record = RecordWithDefaults(
            record_id="R-2",
            tags=["a", "b"],
            metadata={"key": "value"},
            optional_field="present",
        )
        result = record.to_dict()
        assert result["tags"] == ["a", "b"]
        assert result["metadata"] == {"key": "value"}
        assert result["optional_field"] == "present"


class TestDictMixinFromDict:
    """Test from_dict() deserialization."""

    def test_basic_from_dict(self):
        """Should reconstruct dataclass from dict."""
        data = {"name": "test", "value": 42, "active": False}
        record = SimpleRecord.from_dict(data)
        assert record.name == "test"
        assert record.value == 42
        assert record.active is False

    def test_from_dict_ignores_unknown_fields(self):
        """Extra keys in the dict should be silently ignored."""
        data = {"name": "test", "value": 42, "active": True, "unknown_field": "ignored"}
        record = SimpleRecord.from_dict(data)
        assert record.name == "test"
        assert not hasattr(record, "unknown_field")

    def test_from_dict_with_defaults(self):
        """Missing optional fields should use dataclass defaults."""
        data = {"record_id": "R-3"}
        record = RecordWithDefaults.from_dict(data)
        assert record.record_id == "R-3"
        assert record.tags == []
        assert record.metadata == {}
        assert record.optional_field is None


class TestDictMixinRoundTrip:
    """Test to_dict -> from_dict round-trips."""

    def test_simple_round_trip(self):
        """Round-trip should produce identical object."""
        original = SimpleRecord(name="test", value=99, active=False)
        restored = SimpleRecord.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.value == original.value
        assert restored.active == original.active

    def test_complex_round_trip(self):
        """Round-trip with complex fields should preserve all data."""
        original = RecordWithDefaults(
            record_id="R-4",
            tags=["x", "y", "z"],
            metadata={"nested": {"key": "value"}},
            optional_field="filled",
        )
        restored = RecordWithDefaults.from_dict(original.to_dict())
        assert restored.record_id == original.record_id
        assert restored.tags == original.tags
        assert restored.metadata == original.metadata
        assert restored.optional_field == original.optional_field

    def test_dict_equality(self):
        """to_dict output should be equal after round-trip."""
        original = SimpleRecord(name="abc", value=0, active=True)
        assert SimpleRecord.from_dict(original.to_dict()).to_dict() == original.to_dict()
