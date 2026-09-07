"""DaliangOrchestrator：云端编排器对大亮本体的"意图→底盘命令"翻译 + 事件桥接。

这是 MCP-CONTRACT §1（self.suiyue.emote）在大亮本体上的云端侧实现：
- execute_intent() 接收 {emotion, intensity, action_primitive, params}，
  把可执行的动作原语翻译成 self.daliang.* 工具调用；纯表情意图(无动作)委派给 companion-app。
- handle_event() 把底盘 device_event 翻译成对话上下文提示(nudge)，喂给 Agent。

本模块与具体传输无关，可直接作为 xiaozhi-esp32-server fork 的一个 MCP provider 挂载
（提供 tool_schemas() + invoke_tool()）。

依赖：daliang/chassis-gateway 的 daliang_gateway 包（已与真机协议同构，接真机仅改 url）。
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any, Optional

# 让本模块能 import 兄弟目录的 chassis-gateway 包
_CG = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "daliang", "chassis-gateway"))
if _CG not in sys.path:
    sys.path.insert(0, _CG)

from daliang_gateway.gateway import ChassisGateway
from daliang_gateway.client import DaliangChassisClient
from daliang_gateway.mcp_tools import TOOLS

log = logging.getLogger("daliang.orchestrator")

# 云端可显式下发的动作原语（与 MCP-CONTRACT §2 一致）
_CHASSIS_PRIMITIVES = {"approach", "patrol", "navigate", "follow", "dock", "stop"}


class DaliangOrchestrator:
    def __init__(self, gateway: Optional[ChassisGateway] = None,
                 upstream_event: Optional[Any] = None):
        self.gateway = gateway
        self.upstream_event = upstream_event  # 事件双向桥：底盘事件 → 云端/对话

    # -------- 连接 --------
    async def connect(self, url: str) -> None:
        client = DaliangChassisClient(url=url)
        self.gateway = ChassisGateway(client, upstream_event=self._emit_event)
        await self.gateway.start()

    def _emit_event(self, ev: dict) -> None:
        if self.upstream_event:
            self.upstream_event(ev)

    async def close(self) -> None:
        if self.gateway:
            await self.gateway.close()

    # -------- MCP provider 接口（挂载到 xiaozhi-server）--------
    def tool_schemas(self) -> list:
        return TOOLS

    async def invoke_tool(self, tool: str, params: dict) -> Any:
        assert self.gateway is not None, "call connect() first"
        return await self.gateway.invoke(tool, params)

    # -------- 意图执行（MCP-CONTRACT §1: self.suiyue.emote）--------
    async def execute_intent(self, intent: dict) -> dict:
        """把情感意图翻译成底盘动作。

        intent = {
          "emotion": "happy|soothing|concerned|neutral|excited|...",
          "intensity": 0.0-1.0,
          "action_primitive": "approach|patrol|navigate|follow|dock|stop" | null,
          "params": {...}   # 原语参数（如 points / x,y / marker_id）
        }
        返回执行结果；纯表情意图返回委派说明（底盘不动作）。
        """
        primitive = (intent.get("action_primitive") or "").lower()
        if primitive and primitive in _CHASSIS_PRIMITIVES:
            return await self._dispatch_chassis(primitive, intent.get("params") or {})
        # 无动作原语：表情由 companion-app 处理，底盘保持原地
        return {
            "delegated": "expression",
            "to": "companion-app",
            "reason": "intent has no chassis action_primitive; kinesics handled by expression layer",
            "emotion": intent.get("emotion"),
            "intensity": intent.get("intensity"),
        }

    async def _dispatch_chassis(self, primitive: str, params: dict) -> Any:
        tool = "self.daliang.stop_all" if primitive == "stop" else f"self.daliang.{primitive}"
        log.info("daliang intent -> %s %s", tool, params)
        return await self.invoke_tool(tool, params)

    # -------- 看护场景便捷封装 --------
    async def start_care_round(self, marker_ids: list, dwell_s: float = 30.0,
                               loops: int = 0, speed: float = 0.7) -> dict:
        """定时巡游看护：在给定点位间循环巡游，每点停留 dwell_s 秒。
        对应底盘 multiPointCruise，到达每个点会经网关上报 patrol_arrive 事件。"""
        points = [{"id": mid, "time": dwell_s} for mid in marker_ids]
        return await self.invoke_tool("self.daliang.patrol",
                                      {"points": points, "count": loops if loops > 0 else 1, "speed": speed})

    # -------- 事件 → 对话上下文 --------
    @staticmethod
    def handle_event(event: dict) -> Optional[dict]:
        """把底盘 device_event 翻译成 Agent 可消费的上下文提示(nudge)。
        纯函数，无副作用；编排器只负责产出结构化提示，是否进记忆由 Agent 决定。

        返回 None 表示无需对话介入（如普通状态上报）。
        """
        name = event.get("event")
        if name == "patrol_arrive":
            return {"type": "context", "scope": "presence",
                    "message": f"已到达看护点位 {event.get('marker_id')}，可主动问候或关怀。",
                    "marker_id": event.get("marker_id")}
        if name == "navigation_event":
            return {"type": "context", "scope": "presence",
                    "message": f"已走到老人身边（事件 {event.get('id')}），等待对话释放。",
                    "event_id": event.get("id")}
        if name == "event_released":
            return {"type": "context", "scope": "presence",
                    "message": f"对话结束，继续巡游（事件 {event.get('id')} 已释放）。"}
        if name == "goal_reached":
            return {"type": "context", "scope": "presence",
                    "message": f"已到达坐标 ({event.get('x')}, {event.get('y')})。"}
        if name == "emergency_stop":
            return {"type": "alert", "urgent": True,
                    "message": f"大亮已触发软急停（原因：{event.get('reason')}）。停止一切移动。"}
        if name == "battery_low":
            return {"type": "alert",
                    "message": f"大亮电量偏低（{event.get('level')}%），建议安排回桩充电。"}
        return None
