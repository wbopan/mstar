"""Audit configuration for the travel domain."""

from __future__ import annotations

import re
from typing import Any

from state_bench.audits._types import DomainAuditConfig, EntityPattern


def _build_env_index(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "booking_ids": {b["booking_id"] for b in raw.get("bookings", [])},
        "booking_owner": {b["booking_id"]: b["user_id"] for b in raw.get("bookings", [])},
        "flight_ids": {f["flight_id"] for f in raw.get("flights", [])},
        "hotel_ids": {h["reservation_id"] for h in raw.get("hotels", [])},
        "car_ids": {c["rental_id"] for c in raw.get("car_rentals", [])},
        "customer_ids": {u["user_id"] for u in raw.get("users", [])},
    }


def _load_scenarios() -> dict[str, dict[str, Any]]:
    from domains.travel.task_registry import ALL_SCENARIOS, reset_counters

    reset_counters()
    result: dict[str, dict[str, Any]] = {}
    for idx, scenario_fn in enumerate(ALL_SCENARIOS, start=1):
        flights, bookings, task_data = scenario_fn()
        tid = task_data["task_id"]
        numbered_id = f"{idx}-{tid}"
        task_data["_numbered_id"] = numbered_id
        task_data["_scenario_flights"] = flights
        task_data["_scenario_bookings"] = bookings
        result[numbered_id] = task_data
    return result


def get_audit_config() -> DomainAuditConfig:
    from domains.travel.user_attributes import CUSTOMER_ATTRIBUTES

    return DomainAuditConfig(
        name="travel",
        expected_task_count=150,
        entity_patterns=[
            EntityPattern(
                prefix="BK",
                regex=re.compile(r"\bBK-\d+\b"),
                env_lookup_key="booking_ids",
                ownership_field="user_id",
                ownership_lookup_key="booking_owner",
            ),
            EntityPattern(prefix="HR", regex=re.compile(r"\bHR-\d+\b"), env_lookup_key="hotel_ids"),
            EntityPattern(prefix="CR", regex=re.compile(r"\bCR-\d+\b"), env_lookup_key="car_ids"),
        ],
        read_tools={
            "get_booking",
            "get_user_reservations",
            "get_policies",
            "get_flight_status",
            "get_user_details",
            "search_flights",
            "search_hotels",
            "search_car_rentals",
            "get_hotel_reservation",
            "get_car_rental",
        },
        write_tools={
            "cancel_booking",
            "update_booking",
            "create_booking",
            "cancel_hotel_reservation",
            "cancel_car_rental",
        },
        build_env_index=_build_env_index,
        customer_attributes=CUSTOMER_ATTRIBUTES,
        load_scenarios=_load_scenarios,
        policy_math_verifier=None,
    )
