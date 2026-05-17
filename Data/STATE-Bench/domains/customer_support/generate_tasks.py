"""Customer-support-specific task generation hooks."""

from __future__ import annotations

from pathlib import Path

from domains.customer_support.task_registry._builders import _canonical_scenario_template
from state_bench.generation import ReplayPolicy, ScenarioBuildResult
from state_bench.replay import ReplayMatcherConfig


_MATCHER_CONFIG = ReplayMatcherConfig()

CUSTOMER_SUPPORT_TASK_TYPES = frozenset(
    {
        "cancel_order",
        "compound",
        "edge_case",
        "exchange_item",
        "price_match_refund",
        "return_item",
        "shipping_claim",
        "warranty_claim",
    }
)


def _audit_product_lookup(task_data: dict, task_env, replay_trace: list[dict] | None = None) -> list[str]:
    if replay_trace is None:
        from domains.customer_support.task_registry import build_replay_trace

        replay_trace = build_replay_trace(task_data, task_env)

    if not any(isinstance(step, dict) and step.get("name") == "get_product" for step in replay_trace):
        return []

    from domains.customer_support.environment import CustomerSupportEnvironment

    scenario = _canonical_scenario_template(task_data.get("scenario_template", {}))
    now = task_data.get("now") or scenario.get("now")
    if not isinstance(now, str) or not now:
        now = "2026-06-12T10:00:00"
    env = CustomerSupportEnvironment(task_env.deep_copy(), now=now)

    candidate_queries: list[str] = []
    for step in replay_trace:
        if not isinstance(step, dict) or step.get("name") != "get_product":
            continue
        arguments = step.get("arguments", {})
        if isinstance(arguments, dict):
            candidate = arguments.get("product_id")
            if isinstance(candidate, str) and candidate:
                candidate_queries.append(candidate)
    item_id = scenario.get("item_id") or scenario.get("return_item_id")
    if isinstance(item_id, str):
        item = next((row for row in task_env.order_items if row.item_id == item_id), None)
        if item is not None:
            product = next((row for row in task_env.products if row.product_id == item.product_id), None)
            if product is not None:
                candidate_queries.extend([product.product_id, product.name])
                first_token = product.name.split()[0].strip()
                if first_token:
                    candidate_queries.append(first_token)

    new_product_id = scenario.get("new_product_id")
    if isinstance(new_product_id, str):
        product = next((row for row in task_env.products if row.product_id == new_product_id), None)
        if product is not None:
            candidate_queries.extend([product.product_id, product.name])
            first_token = product.name.split()[0].strip()
            if first_token:
                candidate_queries.append(first_token)

    seen: set[str] = set()
    queries = [query for query in candidate_queries if query and not (query in seen or seen.add(query))]
    if not queries:
        return ["get_product appears in replay_steps but no intended product could be inferred from the scenario"]

    for query in queries:
        result = env.get_product({"product_id": query})
        if isinstance(result, dict) and "error" not in result:
            return []

    return [
        "intended product is not resolvable via get_product in task-local env; "
        f"tried queries: {', '.join(queries)}"
    ]


def _load_checked_in_task_requirements(task_id: str) -> list[dict] | None:
    task_path = Path(f"domains/customer_support/tasks/{task_id}.json")
    if not task_path.exists():
        return None
    import json

    raw = json.loads(task_path.read_text())
    requirements = raw.get("task_requirements")
    return requirements if isinstance(requirements, list) else None


class CustomerSupportGenerationAdapter:
    def __init__(self, registry) -> None:
        self.registry = registry

    def enumerate(self, task_id_filter: set[int] | None = None) -> list[tuple[int, object]]:
        self.registry.reset_counters()
        indexed = list(enumerate(self.registry.ALL_SCENARIOS, start=1))
        if task_id_filter is None:
            return indexed
        return [(idx, scenario) for idx, scenario in indexed if idx in task_id_filter]

    def build(self, idx: int, scenario) -> ScenarioBuildResult:
        products, orders, items, warranties, task_data = scenario()
        task_data = dict(task_data)
        task_data["task_id"] = f"{idx}-{task_data['task_id']}"
        scenario_template = _canonical_scenario_template(task_data.get("scenario_template", {}))
        task_data["now"] = scenario_template["now"]
        task_data["task_env_path"] = f"domains/customer_support/task_envs/{task_data['task_id']}.json"
        task_env = self.registry.build_task_environment(products, orders, items, warranties, task_data)
        replay_trace = list(task_data.get("replay_trace") or self.registry.build_replay_trace(task_data, task_env))
        task_data = self.registry.build_public_task_json(task_data)
        task_num = int(task_data["task_id"].split("-", 1)[0])
        checked_in_task_requirements = _load_checked_in_task_requirements(task_data["task_id"])
        if task_num <= 100 and checked_in_task_requirements is not None:
            task_data["task_requirements"] = checked_in_task_requirements
        issues = _audit_product_lookup(task_data, task_env, replay_trace)
        return ScenarioBuildResult(
            task_data=task_data,
            task_env=task_env,
            now=task_data["now"],
            replay_policy=ReplayPolicy.NO_STATE_CHANGE_OK,
            replay_trace=replay_trace,
            audit_issues=issues,
            matcher_config=_MATCHER_CONFIG,
        )


def get_generation_adapter(registry):
    return CustomerSupportGenerationAdapter(registry)


def _derive_replay_gt(registry, domain_config, task_env, task_data: dict):
    """Backward-compatible helper for older customer-support generation tests."""
    from state_bench.replay import compute_replay_trace_hash, derive_state_requirements_from_state_diff, execute_replay_trace

    replay_trace = list(task_data.get("replay_trace") or registry.build_replay_trace(task_data, task_env))
    env = domain_config.environment_class(task_env.deep_copy(), now=task_data["scenario_template"]["now"])
    try:
        _executed, state_diff = execute_replay_trace(env, replay_trace)
    except Exception:
        requirements: list[dict] = []
    else:
        requirements = derive_state_requirements_from_state_diff(state_diff, matcher_config=_MATCHER_CONFIG)
    replay_hash = compute_replay_trace_hash(
        task_id=task_data["task_id"],
        now=task_data["scenario_template"]["now"],
        replay_trace=replay_trace,
        environment_snapshot=task_env.to_dict(),
    )
    return requirements, replay_hash
