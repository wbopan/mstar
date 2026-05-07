"""Shopping tasks for loyalty redemption and account-aware pricing."""

TASK_MODULES = [
    "domains.shopping_assistant.task_registry.task_10_loyalty_points_on_discount",
    "domains.shopping_assistant.task_registry.task_17_welcome_plus_points_compound",
    "domains.shopping_assistant.task_registry.task_18_platinum_loyalty_and_shipping_compound",
    "domains.shopping_assistant.task_registry.task_31_price_drop_loyalty_platinum_compound",
    "domains.shopping_assistant.task_registry.task_36_oos_backorder_loyalty_compound",
    "domains.shopping_assistant.task_registry.task_58_tier_claim_contradicts_account",
    "domains.shopping_assistant.task_registry.task_63_proactive_loyalty_redemption",
    "domains.shopping_assistant.task_registry.task_73_loyalty_redemption_50pct_cap_silent_trim",
    "domains.shopping_assistant.task_registry.task_83_loyalty_below_minimum_honest_decline",
    "domains.shopping_assistant.task_registry.task_93_loyalty_trim_no_restore_on_readd",
]

