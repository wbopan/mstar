"""Mstar — A framework for optimizing text components using LLM-based reflection."""

# Suppress noisy output from dependencies at import time
import warnings
from typing import Any

warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

import litellm  # noqa: E402

litellm.suppress_debug_info = True

from mstar.datasets import load_dataset, register_dataset  # noqa: E402
from mstar.logging.logger import get_logger  # noqa: E402


def configure_cache(*args: Any, **kwargs: Any) -> None:
    from mstar.cache import configure_cache as _configure_cache

    _configure_cache(*args, **kwargs)


def disable_cache() -> None:
    from mstar.cache import disable_cache as _disable_cache

    _disable_cache()


__all__ = [
    "configure_cache",
    "disable_cache",
    "get_logger",
    "load_dataset",
    "register_dataset",
]
