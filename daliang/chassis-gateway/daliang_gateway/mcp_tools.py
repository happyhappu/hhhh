"""self.daliang.* MCP 工具清单与分发。

契约见 ../../docs/MCP-CONTRACT.md §2。本模块只定义工具元数据与一个
与具体传输无关的 handle(gateway, tool, params)；要注册到小智云端 MCP，
只需把这些 handler 包进 xiaozhi-server 的 MCP provider 即可（见 README）。
"""
from __future__ import annotations

from typing import Any

# 工具清单（name / description / JSON-Schema 风格 input_schema）
TOOLS = [
    {
        "name": "self.daliang.navigate",
        "description": "自由导航到坐标（x, y, theta）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "number"},
                "y": {"type": "number"},
                "theta": {"type": "number", "default": 0},
                "speed": {"type": "number", "default": 0.7, "minimum": 0.1, "maximum": 1.5},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "self.daliang.patrol",
        "description": "多点循环巡游看护；到达每个点上报 patrol_arrive，停留 time 秒。",
        "input_schema": {
            "type": "object",
            "properties": {
                "points": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "time": {"type": "number", "default": 0},
                    },
                }},
                "count": {"type": "integer", "default": 1, "minimum": 1},
                "speed": {"type": "number", "default": 0.7},
            },
            "required": ["points"],
        },
    },
    {
        "name": "self.daliang.approach",
        "description": "走到点位并暂停，等待云端 release（'走到老人身边说话'）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "points": {"type": "array", "items": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "number"},
                        "y": {"type": "number"},
                        "t": {"type": "number", "default": 0},
                        "id": {"type": "integer"},
                        "action": {"type": "string", "default": "stop"},
                    },
                }},
            },
            "required": ["points"],
        },
    },
    {
        "name": "self.daliang.follow",
        "description": "速度环遥控（跟随实验用）。x 前进 m/s，t 转向 rad/s。",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "number", "default": 0},
                "y": {"type": "number", "default": 0},
                "t": {"type": "number", "default": 0},
            },
        },
    },
    {
        "name": "self.daliang.get_status",
        "description": "获取位姿/电量/急停/定位置信度（建议 1Hz 轮询）。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "self.daliang.stop_all",
        "description": "软急停，锁定轮子；任何 Agent 可无条件调用。",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "self.daliang.dock",
        "description": "自动回桩充电（go=false 取消充电）。",
        "input_schema": {
            "type": "object",
            "properties": {"go": {"type": "boolean", "default": True}},
        },
    },
    {
        "name": "self.daliang.region",
        "description": "虚拟墙/减速区（geofence）：卧室/卫生间禁入。op=get/set。",
        "input_schema": {
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["get", "set"]},
                "id": {"type": "integer", "default": 0},
                "polygon": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["op"],
        },
    },
]


async def handle(gateway: Any, tool: str, params: dict) -> Any:
    """把 MCP 工具调用翻译成底盘客户端调用。"""
    c = gateway.client
    if tool == "self.daliang.navigate":
        return await c.navigate(params["x"], params.get("y", 0), params.get("theta", 0), params.get("speed", 0.7))
    if tool == "self.daliang.patrol":
        return await c.patrol(params["points"], params.get("count", 1), params.get("speed", 0.7))
    if tool == "self.daliang.approach":
        return await c.approach(params["points"])
    if tool == "self.daliang.follow":
        return await c.follow(params.get("x", 0), params.get("y", 0), params.get("t", 0))
    if tool == "self.daliang.get_status":
        return await c.get_status()
    if tool == "self.daliang.stop_all":
        return await c.stop_all()
    if tool == "self.daliang.dock":
        return await c.dock(params.get("go", True))
    if tool == "self.daliang.region":
        if params.get("op") == "get":
            return await c.get_region()
        return await c.set_region(params.get("id", 0), params.get("polygon", []))
    raise ValueError(f"unknown tool {tool}")
