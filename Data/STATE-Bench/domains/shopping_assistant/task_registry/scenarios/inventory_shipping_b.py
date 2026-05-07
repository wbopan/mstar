"""Shopping tasks for shipping recomputation after cart changes."""

TASK_MODULES = [
    "domains.shopping_assistant.task_registry.task_79_stale_shipping_after_mutation",
    "domains.shopping_assistant.task_registry.task_98_qty_cap_cross_account_workaround",
]

