"""Shopping tasks for promo eligibility and discount application."""

TASK_MODULES = [
    "domains.shopping_assistant.task_registry.task_3_promo_eligibility_trap",
    "domains.shopping_assistant.task_registry.task_6_welcome_vs_promo_conflict",
    "domains.shopping_assistant.task_registry.task_7_category_bundle_vs_promo",
    "domains.shopping_assistant.task_registry.task_8_brand_category_stacking",
    "domains.shopping_assistant.task_registry.task_13_expired_promo_silent_drop",
    "domains.shopping_assistant.task_registry.task_16_welcome_discount_proactive",
    "domains.shopping_assistant.task_registry.task_26_adversarial_fake_promo_code",
    "domains.shopping_assistant.task_registry.task_32_two_promo_bakeoff",
    "domains.shopping_assistant.task_registry.task_38_silent_promo_auto_drop",
    "domains.shopping_assistant.task_registry.task_39_promo_upgrade_opportunity",
]

