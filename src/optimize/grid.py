from __future__ import annotations

import copy
from dataclasses import dataclass
from itertools import product
from typing import Any, Dict, Iterable, List, Tuple


def deep_set(cfg: Dict[str, Any], dotted_key: str, value: Any) -> None:
    """
    Set a nested dictionary value using a dotted key path, e.g.:
      deep_set(cfg, "strategy.quantile", 0.2)
    """
    parts = dotted_key.split(".")
    cur: Dict[str, Any] = cfg
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def deep_get(cfg: Dict[str, Any], dotted_key: str, default: Any = None) -> Any:
    parts = dotted_key.split(".")
    cur: Any = cfg
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur


def expand_grid(grid: Dict[str, List[Any]]) -> List[Dict[str, Any]]:
    """
    Expand a parameter grid into a list of parameter dicts.

    The output order is deterministic (keys sorted).
    """
    if not grid:
        return [{}]

    keys = sorted(grid.keys())
    values = [grid[k] for k in keys]

    combos: List[Dict[str, Any]] = []
    for tup in product(*values):
        combo = {k: v for k, v in zip(keys, tup)}
        combos.append(combo)
    return combos


def apply_overrides(base_config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a deep-copied config with dotted-key overrides applied.
    """
    cfg = copy.deepcopy(base_config)
    for k, v in overrides.items():
        deep_set(cfg, k, v)
    return cfg


