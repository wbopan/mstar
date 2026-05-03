"""Mstar evolution system exports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "CompileError": "mstar.evolution.sandbox",
    "DataItem": "mstar.evolution.types",
    "EvalResult": "mstar.evolution.types",
    "EvolutionLoop": "mstar.evolution.loop",
    "EvolutionRecord": "mstar.evolution.types",
    "EvolutionState": "mstar.evolution.types",
    "ExactMatchScorer": "mstar.evolution.evaluator",
    "FailedCase": "mstar.evolution.types",
    "INITIAL_KB_PROGRAM": "mstar.evolution.prompts",
    "KBProgram": "mstar.evolution.types",
    "LLMJudgeScorer": "mstar.evolution.evaluator",
    "MaxSelection": "mstar.evolution.types",
    "MemoryEvaluator": "mstar.evolution.evaluator",
    "MemoryLogger": "mstar.evolution.toolkit",
    "PoolEntry": "mstar.evolution.types",
    "ProgramPool": "mstar.evolution.types",
    "RecencyDecaySelection": "mstar.evolution.types",
    "Reflector": "mstar.evolution.reflector",
    "SelectionStrategy": "mstar.evolution.types",
    "SoftmaxSelection": "mstar.evolution.types",
    "Toolkit": "mstar.evolution.toolkit",
    "ToolkitConfig": "mstar.evolution.toolkit",
    "compile_kb_program": "mstar.evolution.sandbox",
    "extract_dataclass_schema": "mstar.evolution.sandbox",
    "smoke_test": "mstar.evolution.sandbox",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(_EXPORTS[name])
    value = getattr(module, name)
    globals()[name] = value
    return value
