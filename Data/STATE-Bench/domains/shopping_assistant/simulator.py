"""Shopping assistant domain user simulator prompt builder."""

from __future__ import annotations

from pathlib import Path

from domains.shopping_assistant.schemas import SAEnvironmentData
from domains.shopping_assistant.user_attributes import (
    CUSTOMER_ATTRIBUTES,
    TIER_LABELS,
)
from state_bench.schemas import TaskDefinition

_BASE_RULES_PATH = Path(__file__).resolve().parent / "prompts" / "user_sim_base.md"


def build_simulator_prompt(
    task: TaskDefinition,
    env_data: SAEnvironmentData,
    user_id: str,
) -> str:
    """Assemble the full simulator prompt for a shopping assistant task.

    Order:
    1. Preamble (role + precedence note)
    2. Identity (name, personality, tier, first-time, loyalty points, purchase history)
    3. Task Context (from user_sim_context — sim-safe framing)
    4. Base Rules (static behavioral rules from user_sim_base.md)
    5. Task-Specific Rules (override base rules if conflicting)
    """
    customer = CUSTOMER_ATTRIBUTES.get(user_id, {})
    sim = task.user_simulator

    sections: list[str] = [
        "You are a simulated customer browsing an online store with a shopping assistant. "
        "Your opening message has already been sent. Respond naturally based on the identity, context, and rules below.\n\n"
        "**Important:** Task-specific rules take precedence over base rules if there is a conflict."
    ]

    # --- Identity ---
    name = customer.get("name", "Customer")
    tier = customer.get("tier", "standard")
    tier_label = TIER_LABELS.get(tier, tier)
    is_first_time = customer.get("is_first_time", False)
    loyalty_points = customer.get("loyalty_points", 0)
    purchase_history = customer.get("purchase_history") or []

    identity_lines: list[str] = [
        "## Identity\n",
        f"You are **{name}**.",
        f"- Personality: {sim.personality}",
        f"- Membership tier: {tier_label}",
        f"- First-time customer: {'yes' if is_first_time else 'no'}",
        f"- Loyalty points: {loyalty_points}",
    ]
    if purchase_history:
        identity_lines.append(f"- Past purchases: {', '.join(purchase_history)}")

    # What you know
    know_items = [
        f"Your name is {name}",
        f"Your customer ID is {user_id}",
        f"Your membership tier is {tier_label}",
    ]
    if sim.known_info:
        know_items.extend(sim.known_info)
    identity_lines.append("\n### What you know")
    for item in know_items:
        identity_lines.append(f"- {item}")
    identity_lines.append("\nIf the agent states any of these incorrectly, correct them.")

    # What you don't know
    if sim.unknown_info:
        identity_lines.append("\n### What you don't know")
        for item in sim.unknown_info:
            identity_lines.append(f"- {item}")

    sections.append("\n".join(identity_lines))

    # --- Task Context (sim-safe framing only) ---
    if sim.user_sim_context:
        sections.append(f"## Task Context\n\n{sim.user_sim_context}")

    # --- Base Rules ---
    sections.append(_BASE_RULES_PATH.read_text())

    # --- Task-Specific Rules ---
    if sim.task_rules:
        rule_lines = ["## Task-Specific Rules\n"]
        for i, rule in enumerate(sim.task_rules, 1):
            rule_lines.append(f"{i}. {rule}")
        sections.append("\n".join(rule_lines))

    return "\n\n---\n\n".join(sections)
