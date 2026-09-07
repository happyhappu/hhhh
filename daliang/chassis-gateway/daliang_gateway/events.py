"""事件 -> MCP-CONTRACT device_event 格式化。

契约见 ../../docs/MCP-CONTRACT.md §3。底盘侧事件上行统一为：
{"type":"device_event","event":<名>,"...":<>}
"""
from __future__ import annotations

from typing import Any


def patrol_arrive(marker_id: Any, code: int = 1000) -> dict:
    return {"type": "device_event", "event": "patrol_arrive", "marker_id": marker_id, "code": code}


def patrol_depart(marker_id: Any) -> dict:
    return {"type": "device_event", "event": "patrol_depart", "marker_id": marker_id}


def navigation_event(event_id: Any, action: str) -> dict:
    return {"type": "device_event", "event": "navigation_event", "id": event_id, "action": action}


def event_released(event_id: Any, action: str = "") -> dict:
    return {"type": "device_event", "event": "event_released", "id": event_id, "action": action}


def goal_reached(x: float, y: float) -> dict:
    return {"type": "device_event", "event": "goal_reached", "x": x, "y": y}


def emergency_stop(reason: str) -> dict:
    return {"type": "device_event", "event": "emergency_stop", "reason": reason}


def battery_low(level: int) -> dict:
    return {"type": "device_event", "event": "battery_low", "level": level}
