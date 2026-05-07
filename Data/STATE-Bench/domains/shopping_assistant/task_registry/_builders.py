"""Shopping assistant scenario-builder helpers.

Each scenario function authors products + promotions inline and returns
an SAEnvironmentData snapshot plus the task metadata needed to write
`task_envs/<task_id>.json` and `tasks/<task_id>.json`.

Design:
- Per-task catalogs (20-40 products). Uniqueness of `product.name` enforced
  within each env; cross-env duplicates allowed (envs are isolated).
- Each env pre-creates an empty cart at `CART-<user_id>`. No `post_env_init`.
- Customer record is looked up from `user_attributes.CUSTOMER_ATTRIBUTES`
  and materialized into the env so the environment can serve it.
"""

from __future__ import annotations

from pathlib import Path

from domains.shopping_assistant.schemas import (
    Cart,
    Customer,
    Product,
    Promotion,
    SAEnvironmentData,
)
from domains.shopping_assistant.user_attributes import CUSTOMER_ATTRIBUTES

TASK_ENVS_DIR = Path("domains/shopping_assistant/task_envs")
TASKS_DIR = Path("domains/shopping_assistant/tasks")


def build_customer_record(user_id: str) -> Customer:
    """Build a Customer dataclass from the canonical CUSTOMER_ATTRIBUTES entry."""
    attrs = CUSTOMER_ATTRIBUTES.get(user_id)
    if not attrs:
        raise KeyError(f"Unknown user_id: {user_id}. Not in CUSTOMER_ATTRIBUTES.")
    return Customer(
        customer_id=user_id,
        name=attrs["name"],
        email=attrs["email"],
        tier=attrs.get("tier", "standard"),
        is_first_time=attrs.get("is_first_time", False),
        loyalty_points=attrs.get("loyalty_points", 0),
        purchase_history=list(attrs.get("purchase_history", [])),
    )


def empty_cart_for(user_id: str) -> Cart:
    """Every task starts with an empty cart at the canonical id."""
    return Cart(cart_id=f"CART-{user_id}", customer_id=user_id)


def assert_unique_names(products: list[Product]) -> None:
    seen: set[str] = set()
    for p in products:
        if p.name in seen:
            raise ValueError(f"Duplicate product name within env: {p.name!r}")
        seen.add(p.name)


def assert_unique_ids(products: list[Product]) -> None:
    seen: set[str] = set()
    for p in products:
        if p.product_id in seen:
            raise ValueError(f"Duplicate product_id within env: {p.product_id!r}")
        seen.add(p.product_id)


def build_env(
    user_id: str,
    products: list[Product],
    promotions: list[Promotion] | None = None,
) -> SAEnvironmentData:
    """Assemble an SAEnvironmentData snapshot for one task.

    Embeds only the relevant customer; empty cart at CART-<user_id>; no cart items.
    """
    assert_unique_names(products)
    assert_unique_ids(products)
    customer = build_customer_record(user_id)
    cart = empty_cart_for(user_id)
    return SAEnvironmentData(
        products=products,
        customers=[customer],
        carts=[cart],
        cart_items=[],
        promotions=promotions or [],
    )


def write_task_env(task_id: str, env_data: SAEnvironmentData) -> Path:
    """Write the task env snapshot to domains/shopping_assistant/task_envs/<task_id>.json."""
    TASK_ENVS_DIR.mkdir(parents=True, exist_ok=True)
    path = TASK_ENVS_DIR / f"{task_id}.json"
    env_data.save(path)
    return path


_DEFENSIVE_RULE_MARKER = "[defensive-no-unsolicited-writes]"

DEFENSIVE_SIM_RULES_NO_UNSOLICITED_WRITES: tuple[str, ...] = (
    f"{_DEFENSIVE_RULE_MARKER} Do NOT volunteer anything about loyalty points, shipping options, or "
    "related preferences — these are out of scope for this task.",
    f"{_DEFENSIVE_RULE_MARKER} If the agent asks whether you want to redeem loyalty points or use any "
    "points balance, decline: say 'no, not this time — I don't want to use points.' Do NOT name a "
    "point amount.",
    f"{_DEFENSIVE_RULE_MARKER} If the agent asks about shipping options, expedited shipping, shipping "
    "upgrades, or asks you to pick a shipping method, say 'I don't need to pick shipping right now — "
    "skip it, I'll handle it at checkout.' Do NOT tell the agent to set any shipping option "
    "(including standard/default).",
)


def _inject_defensive_sim_rules(task_json: dict) -> None:
    """Add defensive sim rules for tasks carrying no_unsolicited_new_writes.

    Keeps the sim from volunteering consent for loyalty/shipping writes when the
    task isn't about those topics. Idempotent: strips any prior-injected
    defensive rules (identified by the marker prefix) before re-appending the
    current canonical set, so wording updates propagate cleanly.
    """
    reqs = task_json.get("task_requirements") or []
    if not any(r.get("id") == "no_unsolicited_new_writes" for r in reqs):
        return
    sim = task_json.setdefault("user_simulator", {})
    rules = sim.setdefault("task_rules", [])
    rules[:] = [r for r in rules if _DEFENSIVE_RULE_MARKER not in r]
    rules.extend(DEFENSIVE_SIM_RULES_NO_UNSOLICITED_WRITES)


def write_task(task_json: dict) -> Path:
    """Write a task definition JSON to domains/shopping_assistant/tasks/<task_id>.json."""
    import json

    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    task_json = dict(task_json)
    if "task_info" in task_json:
        raise ValueError(f"{task_json['task_id']} still contains legacy task_info")
    if not task_json.get("task_summary"):
        raise ValueError(f"{task_json['task_id']} is missing task_summary")
    sim = task_json.get("user_simulator", {})
    if not sim.get("user_sim_context"):
        raise ValueError(f"{task_json['task_id']} is missing user_simulator.user_sim_context")
    _inject_defensive_sim_rules(task_json)
    task_id = task_json["task_id"]
    path = TASKS_DIR / f"{task_id}.json"
    with open(path, "w") as f:
        json.dump(task_json, f, indent=2, ensure_ascii=False)
    print(f"Wrote task → {path}")
    return path


def materialize(
    task_id: str,
    env_data: SAEnvironmentData,
    task_json: dict,
) -> tuple[Path, Path]:
    """Write both the env JSON and task JSON. Returns (env_path, task_path)."""
    env_path = write_task_env(task_id, env_data)
    task_json = dict(task_json)
    task_json["task_env_path"] = str(env_path)
    task_path = write_task(task_json)
    return env_path, task_path
