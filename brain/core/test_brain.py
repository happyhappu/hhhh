"""brain/core 单元测试 + 大亮实时集成测试。

运行（在 suiyue/ 根目录）：
    python -m unittest brain.core.test_brain -v
"""
from __future__ import annotations

import asyncio
import os
import sys
import unittest

_CG = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..",
                                    "daliang", "chassis-gateway"))
if _CG not in sys.path:
    sys.path.insert(0, _CG)

from daliang_gateway.mock_server import make_handler  # noqa: E402
from daliang_gateway.world import World  # noqa: E402
from daliang_gateway.client import DaliangChassisClient  # noqa: E402
from daliang_gateway.gateway import ChassisGateway  # noqa: E402

from .brain import SuiyueBrain  # noqa: E402
from .provider import DaliangProvider, StaticProvider  # noqa: E402
from ..daliang_provider.orchestrator import DaliangOrchestrator  # noqa: E402


class TestStaticProviders(unittest.IsolatedAsyncioTestCase):
    async def test_otto_happy_expression(self):
        p = StaticProvider("otto_v1", "otto-01")
        r = await p.emote({"emotion": "happy", "intensity": 0.8})
        self.assertEqual(r.device_model, "otto_v1")
        self.assertIn("swing", r.expression.get("actions", []))
        self.assertIn("waving", r.expression.get("actions", []))
        self.assertIsNone(r.motion)
        self.assertFalse(r.degraded)

    async def test_otto_degrades_locomotion(self):
        p = StaticProvider("otto_v1", "otto-01")
        r = await p.emote({"emotion": "neutral", "intensity": 0.5,
                           "action_primitive": "approach", "params": {"marker_id": "sofa"}})
        self.assertTrue(r.degraded)          # otto 无移动能力
        self.assertIsNone(r.motion)          # 移动原语被忽略
        self.assertIn("approach", r.note)

    async def test_reachy_happy_pose(self):
        p = StaticProvider("reachy_mini_v1", "reachy-01")
        r = await p.emote({"emotion": "happy", "intensity": 0.9})
        expr = r.expression
        self.assertEqual(expr.get("head"), "up")
        self.assertEqual(expr.get("antenna"), "waggle")
        self.assertEqual(expr.get("eyes"), "smile")
        self.assertIsNone(r.motion)

    async def test_daliang_static_expression_delegated(self):
        p = StaticProvider("daliang_v1", "daliang-01")
        r = await p.emote({"emotion": "happy", "intensity": 0.7})
        self.assertEqual(r.expression.get("delegated_to"), "companion-app")
        self.assertIsNone(r.motion)

    async def test_daliang_static_resolves_chassis_primitive(self):
        p = StaticProvider("daliang_v1", "daliang-01")
        r = await p.emote({"emotion": "concerned", "intensity": 0.6,
                           "action_primitive": "approach", "params": {"marker_id": "sofa"}})
        self.assertFalse(r.degraded)         # daliang 有底盘
        self.assertIsNotNone(r.motion)
        self.assertEqual(r.motion["primitive"], "approach")
        self.assertFalse(r.executed)         # 静态模拟未真正执行


class TestBrainDispatch(unittest.IsolatedAsyncioTestCase):
    async def test_dispatch_all_gives_three_distinct_reactions(self):
        brain = SuiyueBrain()
        brain.register("otto-01", "otto_v1")
        brain.register("reachy-01", "reachy_mini_v1")
        brain.register("daliang-01", "daliang_v1")
        results = await brain.dispatch_emote_all({"emotion": "happy", "intensity": 0.8})
        self.assertEqual(set(results), {"otto-01", "reachy-01", "daliang-01"})
        # 三者表情表达各不相同
        self.assertNotEqual(results["otto-01"].expression, results["reachy-01"].expression)
        self.assertNotEqual(results["reachy-01"].expression, results["daliang-01"].expression)
        # daliang 仅表情委派，ottoreachy 有具体姿态
        self.assertIsNone(results["otto-01"].motion)
        self.assertIsNone(results["reachy-01"].motion)

    async def test_unknown_device_raises(self):
        brain = SuiyueBrain()
        with self.assertRaises(KeyError):
            await brain.dispatch_emote("ghost", {"emotion": "happy"})


class TestDaliangLiveIntegration(unittest.IsolatedAsyncioTestCase):
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

    async def asyncTearDown(self):
        await self.orch.close()
        self.server.close()

    async def test_daliang_live_approach_executes(self):
        provider = DaliangProvider(self.orch, device_id="daliang-01")
        r = await provider.emote({"emotion": "concerned", "intensity": 0.6,
                                  "action_primitive": "approach", "params": {"marker_id": self.sofa_id}})
        self.assertTrue(r.executed)
        self.assertEqual(self.world.mode, "event_nav")   # 走到沙发旁暂停


if __name__ == "__main__":
    unittest.main()
