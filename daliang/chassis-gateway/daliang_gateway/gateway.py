"""ChassisGateway：底盘命令 <-> self.daliang.* MCP 工具的翻译层 + 事件上行。

- 北向（云端 -> 本网关）：invoke(tool, params) 分发到 mcp_tools.handle
- 南向（本网关 -> 底盘）：经 DaliangChassisClient 发大亮协议
- 事件上行（底盘 -> 云端）：把底盘事件翻译成 MCP-CONTRACT device_event，经 upstream_event 回调

用途：云端编排器只认 self.daliang.* 与 device_event，不关心底层是 WS 还是 MQTT。
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from .client import DaliangChassisClient
from .events import (
    patrol_arrive, patrol_depart, navigation_event, goal_reached,
    emergency_stop, battery_low,
)
from .mcp_tools import handle as mcp_handle


class ChassisGateway:
    def __init__(self, client: DaliangChassisClient,
                 upstream_event: Optional[Callable[[dict], None]] = None):
        self.client = client
        self.upstream_event = upstream_event

    async def start(self) -> None:
        await self.client.connect()
        self.client.on_event = self._on_chassis_event

    async def invoke(self, tool: str, params: dict) -> Any:
        return await mcp_handle(self, tool, params)

    async def close(self) -> None:
        await self.client.close()

    # ---------------- 事件翻译 ----------------
    def _on_chassis_event(self, msg: dict) -> None:
        ev = self._translate(msg)
        if ev and self.upstream_event:
            self.upstream_event(ev)

    @staticmethod
    def _translate(msg: dict) -> Optional[dict]:
        cmd = msg.get("cmd")
        if cmd == "multiPointCruise_result":
            code = msg.get("code")
            if code == 1000:
                return patrol_arrive(msg.get("data"), 1000)
            if code == 1001:
                return patrol_depart(msg.get("data"))
            return None
        if msg.get("type") == "device_event":
            return msg
        return None
