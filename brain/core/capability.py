"""能力注册表加载器。

各本体的能力注册表放在 `brain/capabilities/<device_model>.yaml`，
云端编排器与端侧编排器共用同一份（ADR-004 / MCP-CONTRACT §1）。
"""
from __future__ import annotations

import os
from typing import Any

import yaml

_CAP_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "capabilities"))


def capability_path(model: str) -> str:
    return os.path.join(_CAP_DIR, f"{model}.yaml")


def load_capability(model: str) -> dict[str, Any]:
    """读取某本体的能力注册表。"""
    p = capability_path(model)
    if not os.path.exists(p):
        raise FileNotFoundError(f"能力注册表不存在: {p}")
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_models() -> list[str]:
    """列出所有已知本体 model 名。"""
    if not os.path.isdir(_CAP_DIR):
        return []
    return sorted(os.path.splitext(f)[0] for f in os.listdir(_CAP_DIR) if f.endswith(".yaml"))
