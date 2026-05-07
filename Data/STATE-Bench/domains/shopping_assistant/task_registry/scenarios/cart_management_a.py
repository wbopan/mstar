"""Shopping tasks for core cart writes and cart hygiene."""

TASK_MODULES = [
    "domains.shopping_assistant.task_registry.task_12_gift_wrap_silent_fee",
    "domains.shopping_assistant.task_registry.task_21_impatient_cheapest_silent_add",
    "domains.shopping_assistant.task_registry.task_25_existing_cart_qty_cap_delta",
    "domains.shopping_assistant.task_registry.task_29_impatient_skip_disclosure_pressure",
    "domains.shopping_assistant.task_registry.task_42_build_a_setup_running_total",
    "domains.shopping_assistant.task_registry.task_43_swap_back_cart_hygiene",
    "domains.shopping_assistant.task_registry.task_45_gift_retracted_wrap_removal",
    "domains.shopping_assistant.task_registry.task_55_partial_add_failure_reporting",
    "domains.shopping_assistant.task_registry.task_60_pause_mid_sequence",
    "domains.shopping_assistant.task_registry.task_69_cart_hygiene_product_swap",
]

