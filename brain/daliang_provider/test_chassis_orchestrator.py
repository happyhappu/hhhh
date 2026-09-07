"""DaliangOrchestrator 集成测试：用底盘模拟器（mock server）验证意图执行 + 事件桥接。

运行：从 suiyue 仓库根目录
  python -m unittest brain.daliang_provider.test_chassis_orchestrator -v
（依赖 daliang/chassis-gateway 的 websockets）
"""
import asyncio
import os
import sys
import unittest

_THIS = os.path.dirname(os.path.abspath(__file__))          # brain/daliang_provider
_BRAIN = os.path.dirname(_THIS)                              # brain
_ROOT = os.path.dirname(_BRAIN)                             # suiyue
_CG = os.path.normpath(os.path.join(_ROOT, "daliang", "chassis-gateway"))
for p in (_CG, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import websockets                                          # noqa: E402
from brain.daliang_provider.orchestrator import DaliangOrchestrator  # noqa: E402
from daliang_gateway.client import DaliangChassisClient     # noqa: E402
from daliang_gateway.gateway import ChassisGateway          # noqa: E402
from daliang_gateway.mock_server import make_handler        # noqa: E402
from daliang_gateway.world import World                    # noqa: E402

_PORT = 7090


class TestDaliangOrchestrator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        global _PORT
        _PORT += 1
        self.port = _PORT
        self.world = World()
        self.server = await websockets.serve(make_handler(self.world), "127.0.0.1", self.port)
        self.orch = DaliangOrchestrator()
        self.events = []
        await self.orch.connect(f"ws://127.0.0.1:{self.port}")
        self.orch.upstream_event = self.events.append
        # 建两个看护点位
        self.m_sofa = await self.orch.gateway.client.marker_add("0715", "sofa", "1", 1.0, 1.0)
        self.m_table = await self.orch.gateway.client.marker_add("0715", "table", "1", -1.5, 0.5)

    async def asyncTearDown(self):
        await self.orch.close()
        self.server.close()

    async def test_tool_schemas_count(self):
        self.assertEqual(len(self.orch.tool_schemas()), 9)

    async def test_execute_intent_approach(self):
        res = await self.orch.execute_intent({
            "emotion": "concerned", "intensity": 0.6, "action_primitive": "approach",
            "params": {"points": [{"id": self.m_sofa, "x": 1.0, "y": 1.0, "t": 0, "action": "stop"}]},
        })
        self.assertEqual(res.get("code"), 0)
        self.assertEqual(self.world.mode, "event_nav")

    async def test_execute_intent_emote_only_delegated(self):
        res = await self.orch.execute_intent({
            "emotion": "happy", "intensity": 0.7, "action_primitive": None, "params": {},
        })
        self.assertEqual(res.get("delegated"), "expression")
        self.assertEqual(res.get("to"), "companion-app")
        # 底盘不应进入任何移动模式
        self.assertEqual(self.world.mode, "idle")

    async def test_execute_intent_stop(self):
        res = await self.orch.execute_intent({
            "emotion": "neutral", "intensity": 0.0, "action_primitive": "stop", "params": {},
        })
        self.assertEqual(res.get("code"), 0)
        self.assertEqual(self.world.wheellock, True)

    async def test_care_round_starts_patrol(self):
        res = await self.orch.start_care_round([self.m_sofa, self.m_table], dwell_s=2.0)
        self.assertEqual(res.get("code"), 0)
        self.assertEqual(self.world.mode, "patrol")

    async def test_event_bridge_patrol_arrive(self):
        await self.orch.start_care_round([self.m_sofa], dwell_s=1.5)
        # 等待到达该点并触发 patrol_arrive 事件
        for _ in range(60):
            if any(e.get("event") == "patrol_arrive" for e in self.events):
                break
            await asyncio.sleep(0.1)
        arrive = [e for e in self.events if e.get("event") == "patrol_arrive"]
        self.assertTrue(arrive, f"未收到 patrol_arrive, events={self.events}")
        nudge = DaliangOrchestrator.handle_event(arrive[0])
        self.assertEqual(nudge["type"], "context")
        # 真实协议上报的是 numeric marker id（非点位名），故断言 id 出现在提示中
        self.assertIn(str(self.m_sofa), nudge["message"])

    async def test_event_bridge_emergency(self):
        ev = {"type": "device_event", "event": "emergency_stop", "reason": "bumper"}
        nudge = DaliangOrchestrator.handle_event(ev)
        self.assertEqual(nudge["type"], "alert")
        self.assertTrue(nudge["urgent"])


if __name__ == "__main__":
    unittest.main()
