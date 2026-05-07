"""Travel-specific task generation hooks."""

from __future__ import annotations

import re

from domains.travel.task_registry._builders import (
    TASK_SUMMARIES,
    USER_SIM_CONTEXTS,
    _augment_user_simulator_rules,
    _normalize_replay_trace,
)
from state_bench.generation import ReplayPolicy, ScenarioBuildResult
from state_bench.replay import ReplayMatcherConfig


_MATCHER_CONFIG = ReplayMatcherConfig(
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
    },
    created_record_fallback_id_field_by_entity={
        "bookings": "booking_id",
        "hotels": "reservation_id",
        "car_rentals": "rental_id",
    },
)


SCENARIO_FAMILY_TO_TASK_TYPE = {
    "adversarial": "adversarial_or_reasoning_trap",
    "booking": "new_booking",
    "cancellations": "cancellation",
    "challenge_boundaries": "flight_change_policy",
    "challenge_discounts": "flight_change_policy",
    "challenge_edge_conflicts": "flight_change_policy",
    "challenge_fee_math": "flight_change_policy",
    "challenge_mixed_strategies": "flight_change_policy",
    "challenge_reasoning_traps": "adversarial_or_reasoning_trap",
    "changes": "flight_change_policy",
    "expansion_changes": "flight_change_policy",
    "expansion_policy": "policy_info_or_restraint",
    "expansion_strategy_challenges": "strategy_compare_paths",
    "expansion_trip_coordination": "multi_booking_trip_coordination",
    "information": "policy_info_or_restraint",
    "policy_disruption": "policy_info_or_restraint",
    "policy_pricing": "policy_info_or_restraint",
    "trip_management": "multi_booking_trip_coordination",
    "trip_planning": "multi_booking_trip_coordination",
}

TRAVEL_TASK_TYPES = frozenset(SCENARIO_FAMILY_TO_TASK_TYPE.values())


def _task_type_for_scenario(scenario) -> str:
    scenario_family = scenario.__module__.rsplit(".", 1)[-1]
    try:
        return SCENARIO_FAMILY_TO_TASK_TYPE[scenario_family]
    except KeyError as exc:
        raise ValueError(f"Unmapped travel scenario family for task_type: {scenario_family}") from exc


def _audit_task_references(task_data: dict, task_env) -> list[str]:
    valid_ids = {
        "booking": {row.booking_id for row in getattr(task_env, "bookings", [])},
        "hotel reservation": {row.reservation_id for row in getattr(task_env, "hotels", [])},
        "car rental": {row.rental_id for row in getattr(task_env, "car_rentals", [])},
    }
    patterns = [
        ("booking", re.compile(r"\bBK-[A-Z0-9]+\b")),
        ("hotel reservation", re.compile(r"\bHR-[A-Z0-9]+\b")),
        ("car rental", re.compile(r"\bCR-[A-Z0-9]+\b")),
    ]

    def _scan(label: str, text: str, issues: list[str]) -> None:
        for entity_label, pattern in patterns:
            for ref in pattern.findall(text or ""):
                if ref not in valid_ids[entity_label]:
                    issues.append(f"{label} references unknown {entity_label}: {ref}")

    issues: list[str] = []
    opening_message = task_data.get("opening_message")
    if isinstance(opening_message, str):
        _scan("opening_message", opening_message, issues)

    task_summary = task_data.get("task_summary")
    if isinstance(task_summary, str):
        _scan("task_summary", task_summary, issues)

    sim = task_data.get("user_simulator", {}) or {}
    user_sim_context = sim.get("user_sim_context")
    if isinstance(user_sim_context, str):
        _scan("user_simulator.user_sim_context", user_sim_context, issues)

    for idx, req in enumerate(task_data.get("task_requirements", []), start=1):
        if isinstance(req, dict):
            requirement = req.get("requirement")
            if isinstance(requirement, str):
                _scan(f"task_requirements[{idx}].requirement", requirement, issues)

    return issues


def _build_public_task_data(task_data: dict) -> dict:
    public_task_data = {k: v for k, v in task_data.items() if not k.startswith("_")}
    if "task_info" in public_task_data:
        raise ValueError(f"{public_task_data['task_id']} still contains legacy task_info")

    user_simulator = public_task_data.setdefault("user_simulator", {})
    task_slug = str(public_task_data.get("task_id", ""))
    if "-" in task_slug:
        task_slug = task_slug.split("-", 1)[1]

    authored_context = USER_SIM_CONTEXTS.get(task_slug)
    inline_context = user_simulator.get("user_sim_context")
    if isinstance(authored_context, str) and authored_context.strip():
        user_simulator["user_sim_context"] = authored_context.strip()
    elif isinstance(inline_context, str) and inline_context.strip():
        user_simulator["user_sim_context"] = inline_context.strip()
    else:
        raise ValueError(f"{public_task_data['task_id']} is missing authored user_sim_context")

    task_summary = TASK_SUMMARIES.get(task_slug)
    inline_summary = public_task_data.get("task_summary")
    if isinstance(task_summary, str) and task_summary.strip():
        public_task_data["task_summary"] = task_summary.strip()
    elif isinstance(inline_summary, str) and inline_summary.strip():
        public_task_data["task_summary"] = inline_summary.strip()
    else:
        raise ValueError(f"{public_task_data['task_id']} is missing authored task_summary")
    return public_task_data


class TravelGenerationAdapter:
    def __init__(self, registry) -> None:
        self.registry = registry

    def enumerate(self, task_id_filter: set[int] | None = None) -> list[tuple[int, object]]:
        self.registry.reset_counters()
        indexed = list(enumerate(self.registry.ALL_SCENARIOS, start=1))
        if task_id_filter is None:
            return indexed
        return [(idx, scenario) for idx, scenario in indexed if idx in task_id_filter]

    def _warm_counters(self, idx: int) -> None:
        self.registry.reset_counters()
        for warm_idx, scenario in enumerate(self.registry.ALL_SCENARIOS, start=1):
            if warm_idx >= idx:
                break
            scenario()

    def build(self, idx: int, scenario) -> ScenarioBuildResult:
        self._warm_counters(idx)
        flights, bookings, task_data = scenario()
        task_data = dict(task_data)
        task_data["task_id"] = f"{idx}-{task_data['task_id']}"
        task_data["task_type"] = _task_type_for_scenario(scenario)
        task_data["task_env_path"] = f"domains/travel/task_envs/{task_data['task_id']}.json"
        replay_trace = _normalize_replay_trace(task_data, bookings)
        task_data["_replay_trace"] = replay_trace
        _augment_user_simulator_rules(task_data)
        task_env = self.registry.build_task_environment(flights, bookings, task_data)
        task_data = _build_public_task_data(task_data)
        issues = _audit_task_references(task_data, task_env)
        return ScenarioBuildResult(
            task_data=task_data,
            task_env=task_env,
            now=task_data["now"],
            replay_policy=ReplayPolicy.STRICT_WRITE_REPLAY,
            replay_trace=replay_trace,
            audit_issues=issues,
            matcher_config=_MATCHER_CONFIG,
        )


def get_generation_adapter(registry):
    return TravelGenerationAdapter(registry)
