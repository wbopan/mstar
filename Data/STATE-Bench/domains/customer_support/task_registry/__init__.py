"""Task registry package for the customer support benchmark."""

from domains.customer_support.task_registry._builders import (
    build_public_task_json,
    build_replay_trace,
    build_task_environment,
    reset_counters,
    save_task,
)
from domains.customer_support.task_registry.scenarios.cancellations import SCENARIOS as CANCELLATION_SCENARIOS
from domains.customer_support.task_registry.scenarios.challenge_advanced_exceptions import (
    SCENARIOS as CHALLENGE_ADVANCED_EXCEPTION_SCENARIOS,
)
from domains.customer_support.task_registry.scenarios.challenge_compounded_outcomes_a import (
    SCENARIOS as CHALLENGE_COMPOUNDED_OUTCOME_A_SCENARIOS,
)
from domains.customer_support.task_registry.scenarios.challenge_compounded_outcomes_b import (
    SCENARIOS as CHALLENGE_COMPOUNDED_OUTCOME_B_SCENARIOS,
)
from domains.customer_support.task_registry.scenarios.challenge_hard_extension import (
    SCENARIOS as CHALLENGE_HARD_EXTENSION_SCENARIOS,
)
from domains.customer_support.task_registry.scenarios.challenge_disputes import SCENARIOS as CHALLENGE_DISPUTE_SCENARIOS
from domains.customer_support.task_registry.scenarios.challenge_fees_loyalty import (
    SCENARIOS as CHALLENGE_FEE_LOYALTY_SCENARIOS,
)
from domains.customer_support.task_registry.scenarios.challenge_policy_clawbacks import (
    SCENARIOS as CHALLENGE_POLICY_CLAWBACK_SCENARIOS,
)
from domains.customer_support.task_registry.scenarios.compound_cases import SCENARIOS as COMPOUND_SCENARIOS
from domains.customer_support.task_registry.scenarios.edge_cases import SCENARIOS as EDGE_SCENARIOS
from domains.customer_support.task_registry.scenarios.exchanges import SCENARIOS as EXCHANGE_SCENARIOS
from domains.customer_support.task_registry.scenarios.returns_refunds import SCENARIOS as RETURN_SCENARIOS
from domains.customer_support.task_registry.scenarios.shipping_delivery import SCENARIOS as SHIPPING_SCENARIOS
from domains.customer_support.task_registry.scenarios.warranty import SCENARIOS as WARRANTY_SCENARIOS

ALL_SCENARIOS = [
    *RETURN_SCENARIOS,
    *CANCELLATION_SCENARIOS,
    *SHIPPING_SCENARIOS,
    *WARRANTY_SCENARIOS,
    *EXCHANGE_SCENARIOS,
    *COMPOUND_SCENARIOS,
    *EDGE_SCENARIOS,
    *CHALLENGE_DISPUTE_SCENARIOS,
    *CHALLENGE_POLICY_CLAWBACK_SCENARIOS,
    *CHALLENGE_FEE_LOYALTY_SCENARIOS,
    *CHALLENGE_ADVANCED_EXCEPTION_SCENARIOS,
    *CHALLENGE_COMPOUNDED_OUTCOME_A_SCENARIOS,
    *CHALLENGE_COMPOUNDED_OUTCOME_B_SCENARIOS,
    *CHALLENGE_HARD_EXTENSION_SCENARIOS,
]

__all__ = [
    "ALL_SCENARIOS",
    "build_public_task_json",
    "build_replay_trace",
    "build_task_environment",
    "reset_counters",
    "save_task",
]
