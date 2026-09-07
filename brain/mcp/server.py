"""SuiyueMCPServer：把 SuiyueBrain 暴露为标准 MCP server（一个大脑三个身体）。

xiaozhi-esp32-server 作为 MCP client 连上本 server 后，LLM 即可通过标准工具调用
驱动三个本体：

- self.suiyue.emote        —— 情感意图（核心，云端下发的统一语言）
- self.suiyue.list_devices —— 列出已注册本体
- self.suiyue.poll_events  —— 拉取底盘/传感事件翻译出的对话上下文提示(nudge)
- self.daliang.* (9)       —— 大亮底盘工具（navigate/patrol/approach/follow/get_status/
                              stop_all/dock/region/add_marker）

本模块传输无关：只产出 MCP 工具清单(list_tools)与调用结果(call_tool)。
stdio / http 等传输见 __main__.py。这样既能直接单测，也能接入任意 MCP client。
"""
from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any, Optional

from ..core.brain import SuiyueBrain
from ..core.provider import DaliangProvider, StaticProvider
from ..daliang_provider.orchestrator import DaliangOrchestrator

# 注入 chassis-gateway 到 sys.path（目录名含连字符，不能作包名）
_CG = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "daliang", "chassis-gateway"))
if _CG not in sys.path:
    sys.path.insert(0, _CG)

from daliang_gateway.gateway import ChassisGateway  # noqa: E402
from daliang_gateway.client import DaliangChassisClient  # noqa: E402
from daliang_gateway.mcp_tools import TOOLS as DALIANG_TOOLS  # noqa: E402

from .config import load_config  # noqa: E402

log = logging.getLogger("suiyue.mcp")

SERVER_NAME = "suiyue-brain"
SERVER_VERSION = "0.1.0"

# ---- 核心工具 schema（MCP-CONTRACT §1）----
_EMOTE_TOOL = {
    "name": "self.suiyue.emote",
    "description": (
        "向岁悦本体下发情感意图。云端只下发 emotion/intensity 与可选 action_primitive，"
        "具体动作由端侧能力注册表决定（一个大脑三个身体）。device_id 省略或 'all' 时广播给所有本体。"
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "device_id": {
                "type": "string",
                "description": "目标本体 id；'all' 或省略=广播给全部已注册本体",
                "default": "all",
            },
            "emotion": {
                "type": "string",
                "description": "情感标签 happy/sad/curious/concerned/neutral/excited/soothing ...",
            },
            "intensity": {"type": "number", "default": 0.5, "minimum": 0.0, "maximum": 1.0},
            "action_primitive": {
                "type": "string",
                "description": "可选：显式动作原语 approach/patrol/navigate/follow/dock/stop（端侧有权忽略，安全优先）",
                "enum": ["approach", "patrol", "navigate", "follow", "dock", "stop"],
            },
            "params": {
                "type": "object",
                "description": "原语参数，如 {marker_id} / {x, y, theta, speed}",
            },
        },
        "required": ["emotion"],
    },
}

_LIST_DEVICES_TOOL = {
    "name": "self.suiyue.list_devices",
    "description": "列出当前已注册到大脑的本体 device_id 列表（用于运维/排障）。",
    "inputSchema": {"type": "object", "properties": {}},
}

_POLL_EVENTS_TOOL = {
    "name": "self.suiyue.poll_events",
    "description": (
        "拉取底盘/传感事件经 DaliangOrchestrator.handle_event 翻译出的对话上下文提示(nudge)。"
        "例如大亮巡游到达看护点位、软急停、低电量等。返回最近 limit 条。"
    ),
    "inputSchema": {
        "type": "object",
        "properties": {"limit": {"type": "integer", "default": 10, "minimum": 1, "maximum": 200}},
    },
}


def _text(payload: Any) -> dict:
    """构造 MCP tools/call 的成功 result（text content）。"""
    return {
        "content": [
            {"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}
        ]
    }


def _error(msg: str, is_error: bool = True) -> dict:
    """构造 MCP tools/call 的错误 result。"""
    return {"content": [{"type": "text", "text": msg}], "isError": is_error}


class SuiyueMCPServer:
    def __init__(self) -> None:
        self.brain = SuiyueBrain()
        self.daliang: Optional[DaliangOrchestrator] = None
        self._event_log: list[dict] = []

    # ---------------- 启动：按配置注册本体 ----------------
    async def setup(self, config: Optional[dict] = None) -> None:
        """按配置文件注册本体到大脑。

        - provider=static：用 StaticProvider 模拟固件（ottoreachy 未接真机时）；
        - provider=daliang：建 DaliangOrchestrator 并视 chassis.url 连真机/留空。
        """
        config = config or load_config()
        devices = config.get("devices", [])
        if not devices:
            raise ValueError("配置中未声明任何 device（至少要有一个本体）")
        for d in devices:
            did = d["device_id"]
            model = d["model"]
            prov = d.get("provider", "static")
            if prov == "daliang":
                orch = DaliangOrchestrator(upstream_event=self._on_event)
                chassis = d.get("chassis", {})
                url = chassis.get("url")
                if url:
                    try:
                        await orch.connect(url)
                        log.info("daliang 底盘已连接: %s", url)
                    except Exception as e:  # 机器人离线/网络不可达时，server 仍要起来
                        orch.gateway = None  # 复位半连接状态，走"网关未启动"干净分支
                        log.warning("daliang 底盘连接失败（%s），provider 已注册但网关未启动，"
                                    "self.daliang.* 调用将返回错误而非崩溃。", e)
                else:
                    log.warning("daliang 未配置 chassis.url，仅注册 provider（不连底盘）")
                self.daliang = orch
                self.brain.register(did, model, DaliangProvider(orch, device_id=did))
            else:
                self.brain.register(did, model)  # StaticProvider 模拟固件
        log.info("MCP server 已注册本体: %s", self.brain.device_ids)

    def _on_event(self, ev: dict) -> None:
        """底盘事件 → 对话上下文提示，入内存日志供 poll_events 拉取。"""
        nudge = DaliangOrchestrator.handle_event(ev)
        self._event_log.append({"event": ev, "nudge": nudge})
        if len(self._event_log) > 200:
            self._event_log.pop(0)

    # ---------------- MCP 工具清单 ----------------
    async def list_tools(self) -> list[dict]:
        tools = [_EMOTE_TOOL, _LIST_DEVICES_TOOL, _POLL_EVENTS_TOOL]
        for t in DALIANG_TOOLS:
            tools.append(
                {
                    "name": t["name"],
                    "description": t["description"],
                    "inputSchema": t["input_schema"],
                }
            )
        return tools

    # ---------------- MCP 工具调用 ----------------
    async def call_tool(self, name: str, args: Optional[dict] = None) -> dict:
        """返回 MCP tools/call 的 result 体（{content:[...]} 或带 isError）。"""
        args = args or {}
        try:
            if name == "self.suiyue.emote":
                return await self._emote(args)
            if name == "self.suiyue.list_devices":
                return _text(self.brain.device_ids)
            if name == "self.suiyue.poll_events":
                limit = int(args.get("limit", 10))
                return _text(self._event_log[-limit:])
            if name.startswith("self.daliang."):
                return await self._daliang_tool(name, args)
            return _error(f"未知工具: {name}")
        except Exception as e:  # 任何异常都作为 MCP 错误返回，不崩 server
            log.exception("tool %s failed", name)
            return _error(f"{type(e).__name__}: {e}", is_error=True)

    async def _emote(self, args: dict) -> dict:
        intent = {
            "emotion": args.get("emotion", "neutral"),
            "intensity": float(args.get("intensity", 0.5)),
            "action_primitive": args.get("action_primitive"),
            "params": args.get("params", {}) or {},
        }
        target = (args.get("device_id") or "all").strip().lower()
        if target == "all":
            results = await self.brain.dispatch_emote_all(intent)
        else:
            results = {target: await self.brain.dispatch_emote(target, intent)}
        return _text({k: v.to_dict() for k, v in results.items()})

    async def _daliang_tool(self, name: str, args: dict) -> dict:
        if self.daliang is None:
            return _error(
                "大亮底盘未连接（MCP server 配置中未启用 daliang provider）", is_error=True
            )
        if self.daliang.gateway is None:
            return _error("大亮底盘网关未启动（chassis.url 不可达）", is_error=True)
        result = await self.daliang.invoke_tool(name, args)
        return _text(result)

    # ---------------- 关闭 ----------------
    async def shutdown(self) -> None:
        if self.daliang:
            await self.daliang.close()
