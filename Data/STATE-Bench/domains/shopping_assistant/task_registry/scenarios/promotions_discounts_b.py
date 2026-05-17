"""Shopping tasks for promo recomputation and discount conflicts."""

TASK_MODULES = [
    "domains.shopping_assistant.task_registry.task_52_invalid_promo_tool_error_recovery",
    "domains.shopping_assistant.task_registry.task_65_bundle_free_shipping_threshold",
    "domains.shopping_assistant.task_registry.task_70_expired_promo_stale_seeded_total",
    "domains.shopping_assistant.task_registry.task_71_two_promo_codes_additive_stack",
    "domains.shopping_assistant.task_registry.task_72_welcome_plus_promo_silent_double_dip",
    "domains.shopping_assistant.task_registry.task_74_redemption_vs_welcome_non_combinable",
    "domains.shopping_assistant.task_registry.task_96_promo_rejected_min_purchase_path",
]

