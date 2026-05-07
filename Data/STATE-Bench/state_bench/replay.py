from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from state_bench.schemas import StateDiff

BOOKING_PERSISTED_PREFERENCE_FIELDS = (
    "meal_preference",
    "cabin_class",
    "seat_type",
    "add_wifi",
    "add_extra_legroom",
    "add_insurance",
)


class ReplayError(RuntimeError):
    """Raised when a canonical replay trace cannot be executed deterministically."""


@dataclass(frozen=True)
class ReplayMatcherConfig:
    created_record_match_priority_by_entity: dict[str, tuple[str, ...]] = field(default_factory=dict)
    created_record_ignored_fields_by_entity: dict[str, set[str]] = field(default_factory=dict)
    created_record_fallback_id_field_by_entity: dict[str, str] = field(default_factory=dict)


DEFAULT_MATCHER_CONFIG = ReplayMatcherConfig(
    created_record_match_priority_by_entity={
        "bookings": (
            "user_id",
            "flight_id",
            "status",
            "payment_method",
            "cash_amount",
            "points_used",
            "cabin_class",
            "seat_type",
            "meal_preference",
            "add_wifi",
            "add_extra_legroom",
            "add_insurance",
            "paid_checked_bags",
        ),
        "hotels": ("user_id", "hotel_id", "check_in", "check_out", "status", "room_type"),
        "car_rentals": ("user_id", "car_id", "pickup_date", "dropoff_date", "status", "car_class"),
        "cart_items": ("customer_id", "product_id", "variant_id", "gift_wrap", "quantity"),
    },
    created_record_ignored_fields_by_entity={
        "cart_items": {"cart_item_id", "customer_id", "product_id", "variant_id", "gift_wrap", "quantity"},
    },
    created_record_fallback_id_field_by_entity={
        "bookings": "booking_id",
        "hotels": "reservation_id",
        "car_rentals": "rental_id",
    },
)


@dataclass
class ReplayStepResult:
    index: int
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any] | Any
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "arguments": self.arguments,
            "result": self.result,
            "error": self.error,
        }


def execute_replay_trace(environment: Any, replay_trace: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], StateDiff]:
    before = environment.get_full_snapshot()
    executed: list[dict[str, Any]] = []

    for index, step in enumerate(replay_trace):
        if not isinstance(step, dict):
            raise ReplayError(f"Replay step {index} must be a dict, got {type(step).__name__}.")
        name = step.get("name")
        arguments = step.get("arguments", {})
        if not name or not isinstance(name, str):
            raise ReplayError(f"Replay step {index} is missing a valid tool name.")
        if not isinstance(arguments, dict):
            raise ReplayError(f"Replay step {index} arguments for {name} must be a dict.")

        handler = getattr(environment, name, None)
        if not callable(handler):
            raise ReplayError(f"Replay step {index} references unknown tool handler {name!r}.")

        try:
            result = handler(arguments)
        except Exception as exc:  # pragma: no cover - defensive
            executed.append(ReplayStepResult(index=index, name=name, arguments=arguments, result={}, error=str(exc)).to_dict())
            raise ReplayError(f"Replay step {index} {name} raised {exc!r}.") from exc

        executed.append(ReplayStepResult(index=index, name=name, arguments=arguments, result=result).to_dict())

        if isinstance(result, dict) and "error" in result:
            raise ReplayError(f"Replay step {index} {name} returned error: {result['error']}")
        if isinstance(result, dict) and result.get("status") == "rejected":
            raise ReplayError(f"Replay step {index} {name} was rejected: {result}")

    after = environment.get_full_snapshot()
    return executed, StateDiff.compute(before, after)


def derive_state_requirements_from_state_diff(
    state_diff: StateDiff,
    matcher_config: ReplayMatcherConfig | None = None,
    **_legacy_kwargs: Any,
) -> list[dict[str, Any]]:
    config = matcher_config or DEFAULT_MATCHER_CONFIG
    requirements: list[dict[str, Any]] = []

    for entity_type in sorted(state_diff.modified):
        for record_key in sorted(state_diff.modified[entity_type]):
            changes = state_diff.modified[entity_type][record_key]
            for field in sorted(changes):
                requirements.append(
                    {
                        "entity_type": entity_type,
                        "record_key": record_key,
                        "field": field,
                        "expected_value": changes[field].get("new"),
                    }
                )

    for entity_type in sorted(state_diff.created):
        records = state_diff.created[entity_type]
        for record_key in sorted(records):
            record = records[record_key]
            match_fields = _derive_match_fields(entity_type, record_key, record, records, config)
            if match_fields == {"record_key": record_key}:
                for field in sorted(record):
                    requirements.append(
                        {
                            "entity_type": entity_type,
                            "record_key": record_key,
                            "field": field,
                            "expected_value": record[field],
                        }
                    )
                continue

            ignored_fields = config.created_record_ignored_fields_by_entity.get(entity_type, set())
            expected_fields = {
                field: record[field]
                for field in sorted(record)
                if field not in ignored_fields
            }
            requirements.append(
                {
                    "entity_type": entity_type,
                    "match_fields": match_fields,
                    "expected_fields": expected_fields,
                }
            )

    return requirements


def compute_replay_trace_hash(task_id: str, now: str, replay_trace: list[dict[str, Any]], environment_snapshot: dict[str, Any]) -> str:
    payload = {
        "task_id": task_id,
        "now": now,
        "replay_trace": replay_trace,
        "environment": environment_snapshot,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _derive_match_fields(
    entity_type: str,
    record_key: str,
    record: dict[str, Any],
    sibling_records: dict[str, dict[str, Any]],
    config: ReplayMatcherConfig,
) -> dict[str, Any]:
    prioritized_fields = config.created_record_match_priority_by_entity.get(entity_type, ())

    candidate: dict[str, Any] = {}
    for field in prioritized_fields:
        if field not in record:
            continue
        candidate[field] = record[field]
        if _match_count(candidate, sibling_records) == 1:
            return _strengthen_match_fields(candidate, prioritized_fields, record)

    fallback_id_field = config.created_record_fallback_id_field_by_entity.get(entity_type)
    if fallback_id_field and fallback_id_field in record:
        return {fallback_id_field: record[fallback_id_field]}

    return {"record_key": record_key}


def _strengthen_match_fields(candidate: dict[str, Any], prioritized_fields: tuple[str, ...], record: dict[str, Any]) -> dict[str, Any]:
    strengthened = dict(candidate)
    for field in prioritized_fields:
        if field in strengthened or field not in record:
            continue
        value = record[field]
        if value is None:
            continue
        strengthened[field] = value
    return strengthened


def _match_count(candidate: dict[str, Any], sibling_records: dict[str, dict[str, Any]]) -> int:
    return sum(1 for sibling in sibling_records.values() if all(sibling.get(field) == value for field, value in candidate.items()))
