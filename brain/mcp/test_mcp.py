"""brain/mcp 测试：MCP 工具清单 + 调用语义（含大亮实时集成）。

运行（在 suiyue/ 根目录，venv 激活）：
    python -m unittest brain.mcp.test_mcp -v

无需任何硬件：大亮实时段用本仓自带的底盘模拟器（与真机协议同构）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest

# 注入 chassis-gateway 到 sys.path（目录名含连字符，不能作包名）
_CG = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "daliang", "chassis-gateway"))
if _CG not in sys.path:
    sys.path.insert(0, _CG)

from daliang_gateway.mock_server import make_handler  # noqa: E402
from daliang_gateway.world import World  # noqa: E402
from daliang_gateway.client import DaliangChassisClient  # noqa: E402
from daliang_gateway.gateway import ChassisGateway  # noqa: E402

from .server import SuiyueMCPServer  # noqa: E402
from ..core.provider import DaliangProvider  # noqa: E402
from ..daliang_provider.orchestrator import DaliangOrchestrator  # noqa: E402


def _payload(res: dict):
    """从 MCP result 取出 text content 并 JSON 解析。"""
    return json.loads(res["content"][0]["text"])


class TestMCPToolsList(unittest.IsolatedAsyncioTestCase):
    async def test_list_includes_core_and_daliang(self):
        s = SuiyueMCPServer()
        orch = DaliangOrchestrator()
        s.daliang = orch
        s.brain.register("otto-01", "otto_v1")
        s.brain.register("reachy-01", "reachy_mini_v1")
        s.brain.register("daliang-01", "daliang_v1", DaliangProvider(orch, "daliang-01"))

        tools = await s.list_tools()
        names = {t["name"] for t in tools}

        # 核心工具
        self.assertIn("self.suiyue.emote", names)
        self.assertIn("self.suiyue.list_devices", names)
        self.assertIn("self.suiyue.poll_events", names)
        # 9 个大亮底盘工具
        for d in [
            "self.daliang.navigate", "self.daliang.patrol", "self.daliang.approach",
            "self.daliang.follow", "self.daliang.get_status", "self.daliang.stop_all",
            "self.daliang.dock", "self.daliang.region", "self.daliang.add_marker",
        ]:
            self.assertIn(d, names)
        # schema 合规：每个工具都有 object 类型 inputSchema
        for t in tools:
            self.assertEqual(t["inputSchema"]["type"], "object")
        # emote 的必填项包含 emotion
        emote = next(t for t in tools if t["name"] == "self.suiyue.emote")
        self.assertIn("emotion", emote["inputSchema"]["required"])


class TestMCPEmote(unittest.IsolatedAsyncioTestCase):
    async def _server(self) -> SuiyueMCPServer:
        s = SuiyueMCPServer()
        s.brain.register("otto-01", "otto_v1")
        s.brain.register("reachy-01", "reachy_mini_v1")
        s.brain.register("daliang-01", "daliang_v1")
        return s

    async def test_emote_all_distinct(self):
        s = await self._server()
        res = await s.call_tool("self.suiyue.emote", {"emotion": "happy", "intensity": 0.8})
        self.assertIsNone(res.get("isError"))
        payload = _payload(res)
        self.assertEqual(set(payload), {"otto-01", "reachy-01", "daliang-01"})
        # 三者表情表达各不相同
        self.assertNotEqual(payload["otto-01"]["expression"], payload["reachy-01"]["expression"])
        self.assertNotEqual(payload["reachy-01"]["expression"], payload["daliang-01"]["expression"])

    async def test_emote_single_device(self):
        s = await self._server()
        res = await s.call_tool("self.suiyue.emote", {"device_id": "otto-01", "emotion": "happy"})
        payload = _payload(res)
        self.assertEqual(list(payload), ["otto-01"])

    async def test_emote_unknown_device_errors(self):
        s = await self._server()
        res = await s.call_tool("self.suiyue.emote", {"device_id": "ghost", "emotion": "happy"})
        self.assertTrue(res.get("isError"))

    async def test_list_devices(self):
        s = await self._server()
        res = await s.call_tool("self.suiyue.list_devices", {})
        self.assertEqual(_payload(res), ["otto-01", "reachy-01", "daliang-01"])

    async def test_unknown_tool_errors(self):
        s = await self._server()
        res = await s.call_tool("self.foo.bar", {})
        self.assertTrue(res.get("isError"))

    async def test_emote_with_action_primitive_resolves_motion(self):
        s = await self._server()
        res = await s.call_tool("self.suiyue.emote",
                                {"emotion": "concerned", "intensity": 0.6,
                                 "action_primitive": "approach", "params": {"marker_id": "sofa"},
                                 "device_id": "daliang-01"})
        payload = _payload(res)
        d = payload["daliang-01"]
        self.assertFalse(d["degraded"])  # daliang 有底盘，原语不降级
        self.assertEqual(d["motion"]["primitive"], "approach")


class TestMCPDaliangLive(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import websockets

        self.world = World()
        self.server = await websockets.serve(make_handler(self.world), "127.0.0.1", 0)
        port = self.server.sockets[0].getsockname()[1]
        self.orch = DaliangOrchestrator()
        client = DaliangChassisClient(url=f"ws://127.0.0.1:{port}")
        self.orch.gateway = ChassisGateway(client)
        await self.orch.gateway.start()
        self.sofa_id = await self.orch.invoke_tool("self.daliang.add_marker",
                                    {"map_name": "home", "name": "sofa", "floor": "1",
                                     "x": 1.0, "y": 1.0, "t": 0.0, "mtype": 1})
        self.s = SuiyueMCPServer()
        self.s.daliang = self.orch
        self.s.brain.register("daliang-01", "daliang_v1", DaliangProvider(self.orch, "daliang-01"))

    async def asyncTearDown(self):
        await self.orch.close()
        self.server.close()

    async def test_daliang_approach_via_mcp(self):
        res = await self.s.call_tool("self.daliang.approach", {"marker_id": self.sofa_id})
        self.assertIsNone(res.get("isError"))
        self.assertEqual(self.world.mode, "event_nav")  # 走到沙发旁暂停，等云端 release

    async def test_daliang_get_status_via_mcp(self):
        res = await self.s.call_tool("self.daliang.get_status", {})
        self.assertIsNone(res.get("isError"))
        status = _payload(res)
        self.assertIn("pos", status)  # 真机/模拟器返回的位姿字段

    async def test_daliang_tool_without_gateway_errors(self):
        s2 = SuiyueMCPServer()  # 未注册 daliang
        res = await s2.call_tool("self.daliang.get_status", {})
        self.assertTrue(res.get("isError"))

    async def test_poll_events_after_event(self):
        # 触发行人事件：approach 走到沙发 -> 模拟事件导航到达回调
        await self.s.call_tool("self.daliang.approach", {"marker_id": self.sofa_id})
        # 让世界 tick 几帧以产生 navigation_event（mock 内部推进）
        await asyncio.sleep(0.3)
        res = await self.s.call_tool("self.suiyue.poll_events", {"limit": 5})
        # 即使无事件，poll 也应返回列表而非错误
        self.assertIsNone(res.get("isError"))
        self.assertIsInstance(_payload(res), list)


if __name__ == "__main__":
    unittest.main()
