"""场景包目录（ADR-007 / ADR-012）。

`brain/packs/` 下每个子目录是一个场景包；`loader.py` 负责加载与继承合并。
本 __init__ 仅做最小暴露，避免循环依赖（brain.core 才依赖 loader）。
"""
from .loader import (
    DEFAULT_SCENE,
    ResolvedPack,
    discover_packs,
    load_pack_raw,
    load_resolved,
    resolve_inheritance,
    select_by_model,
    validate_pack,
)

__all__ = [
    "DEFAULT_SCENE",
    "ResolvedPack",
    "discover_packs",
    "load_pack_raw",
    "load_resolved",
    "resolve_inheritance",
    "select_by_model",
    "validate_pack",
]
