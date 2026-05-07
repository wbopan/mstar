"""Hard shopping extension task 106: hard_compat_unknown_device_canonicalize."""

from __future__ import annotations

from domains.shopping_assistant.task_registry.hard_extension import env_for, task_json_for

TASK_ID = "106-hard_compat_unknown_device_canonicalize"
TASK_JSON = task_json_for("hard_compat_unknown_device_canonicalize")


def _build_seeded_env():
    return env_for("hard_compat_unknown_device_canonicalize")
