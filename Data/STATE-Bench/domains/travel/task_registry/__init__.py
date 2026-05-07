"""Travel domain task registry.

Exports shared builders plus one canonical scenario list assembled from
semantic scenario families.
"""

from domains.travel.task_registry._builders import (
    USERS,
    build_booking,
    build_car_rental,
    build_flight,
    build_hotel,
    build_route_flights,
    build_task_environment,
    reset_counters,
    save_task,
)
from domains.travel.task_registry.scenarios.adversarial import SCENARIOS as ADVERSARIAL_SCENARIOS
from domains.travel.task_registry.scenarios.booking import SCENARIOS as BOOKING_SCENARIOS
from domains.travel.task_registry.scenarios.cancellations import SCENARIOS as CANCELLATION_SCENARIOS
from domains.travel.task_registry.scenarios.challenge_boundaries import SCENARIOS as CHALLENGE_BOUNDARY_SCENARIOS
from domains.travel.task_registry.scenarios.challenge_discounts import SCENARIOS as CHALLENGE_DISCOUNT_SCENARIOS
from domains.travel.task_registry.scenarios.challenge_edge_conflicts import (
    SCENARIOS as CHALLENGE_EDGE_CONFLICT_SCENARIOS,
)
from domains.travel.task_registry.scenarios.challenge_fee_math import SCENARIOS as CHALLENGE_FEE_MATH_SCENARIOS
from domains.travel.task_registry.scenarios.challenge_mixed_strategies import (
    SCENARIOS as CHALLENGE_MIXED_STRATEGY_SCENARIOS,
)
from domains.travel.task_registry.scenarios.challenge_reasoning_traps import (
    SCENARIOS as CHALLENGE_REASONING_TRAP_SCENARIOS,
)
from domains.travel.task_registry.scenarios.changes import SCENARIOS as CHANGE_SCENARIOS
from domains.travel.task_registry.scenarios.expansion_changes import SCENARIOS as EXPANSION_CHANGE_SCENARIOS
from domains.travel.task_registry.scenarios.expansion_policy import SCENARIOS as EXPANSION_POLICY_SCENARIOS
from domains.travel.task_registry.scenarios.expansion_strategy_challenges import SCENARIOS as EXPANSION_STRATEGY_CHALLENGE_SCENARIOS
from domains.travel.task_registry.scenarios.expansion_trip_coordination import SCENARIOS as EXPANSION_TRIP_COORDINATION_SCENARIOS
from domains.travel.task_registry.scenarios.information import SCENARIOS as INFORMATION_SCENARIOS
from domains.travel.task_registry.scenarios.policy_disruption import SCENARIOS as POLICY_DISRUPTION_SCENARIOS
from domains.travel.task_registry.scenarios.policy_pricing import SCENARIOS as POLICY_PRICING_SCENARIOS
from domains.travel.task_registry.scenarios.trip_management import SCENARIOS as TRIP_MANAGEMENT_SCENARIOS
from domains.travel.task_registry.scenarios.trip_planning import SCENARIOS as TRIP_PLANNING_SCENARIOS

ALL_SCENARIOS = [
    *CANCELLATION_SCENARIOS,
    *BOOKING_SCENARIOS,
    *CHANGE_SCENARIOS,
    *POLICY_PRICING_SCENARIOS,
    *POLICY_DISRUPTION_SCENARIOS,
    *TRIP_MANAGEMENT_SCENARIOS,
    *TRIP_PLANNING_SCENARIOS,
    *INFORMATION_SCENARIOS,
    *ADVERSARIAL_SCENARIOS,
    *CHALLENGE_FEE_MATH_SCENARIOS,
    *CHALLENGE_DISCOUNT_SCENARIOS,
    *CHALLENGE_REASONING_TRAP_SCENARIOS,
    *CHALLENGE_BOUNDARY_SCENARIOS,
    *CHALLENGE_EDGE_CONFLICT_SCENARIOS,
    *CHALLENGE_MIXED_STRATEGY_SCENARIOS,
    *EXPANSION_CHANGE_SCENARIOS,
    *EXPANSION_POLICY_SCENARIOS,
    *EXPANSION_TRIP_COORDINATION_SCENARIOS,
    *EXPANSION_STRATEGY_CHALLENGE_SCENARIOS,
]

__all__ = [
    "ALL_SCENARIOS",
    "USERS",
    "build_booking",
    "build_car_rental",
    "build_task_environment",
    "build_flight",
    "build_hotel",
    "build_route_flights",
    "reset_counters",
    "save_task",
]
