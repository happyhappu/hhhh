"""MCP server 启动配置加载器。

配置文件（默认 brain/mcp/config.yaml）描述启动时注册进 SuiyueBrain 的本体与连接方式。
xiaozhi-esp32-server 启动本 MCP server 时通过 --config 指向该文件。
"""
from __future__ import annotations

import os
from typing import Any

import yaml

DEFAULT_CONFIG = os.path.normpath(os.path.join(os.path.dirname(__file__), "config.yaml"))


def load_config(path: str | None = None) -> dict[str, Any]:
    """读取 MCP server 配置。

    - path=None 时使用同目录的 config.yaml；
    - 文件不存在直接抛错，避免静默用空配置导致"未注册任何本体"。
    """
    path = path or DEFAULT_CONFIG
    if not os.path.exists(path):
        raise FileNotFoundError(f"MCP 配置不存在: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
