"""Shopping tasks for stock, shipping, and timing constraints."""

TASK_MODULES = [
    "domains.shopping_assistant.task_registry.task_15_oos_no_silent_substitute",
    "domains.shopping_assistant.task_registry.task_20_triple_policy_compound_disclosure",
    "domains.shopping_assistant.task_registry.task_24_impatient_qty_cap_silent_truncate",
    "domains.shopping_assistant.task_registry.task_40_checkout_oos_stock_audit",
    "domains.shopping_assistant.task_registry.task_49_audit_timing_resumed_checkout",
    "domains.shopping_assistant.task_registry.task_51_qty_cap_tool_error_recovery",
    "domains.shopping_assistant.task_registry.task_75_free_shipping_threshold_vs_qty_cap",
    "domains.shopping_assistant.task_registry.task_78_backorder_deposit_math_disclosure",
    "domains.shopping_assistant.task_registry.task_86_final_total_includes_shipping_disclosure",
    "domains.shopping_assistant.task_registry.task_89_stock_exactly_sufficient_regression_guard",
]

