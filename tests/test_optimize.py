import copy

from src.optimize.grid import apply_overrides, deep_get, deep_set, expand_grid


def test_expand_grid_deterministic():
    grid = {
        "b.x": [1, 2],
        "a.y": ["u", "v"],
    }
    combos = expand_grid(grid)
    # keys sorted => a.y then b.x, product order => u/1, u/2, v/1, v/2
    assert combos[0] == {"a.y": "u", "b.x": 1}
    assert combos[1] == {"a.y": "u", "b.x": 2}
    assert combos[2] == {"a.y": "v", "b.x": 1}
    assert combos[3] == {"a.y": "v", "b.x": 2}


def test_deep_set_and_apply_overrides():
    base = {"a": {"b": 1}, "x": 5}
    ovr = {"a.b": 9, "a.c": 2}
    new_cfg = apply_overrides(base, ovr)
    assert base["a"]["b"] == 1  # unchanged
    assert new_cfg["a"]["b"] == 9
    assert new_cfg["a"]["c"] == 2


