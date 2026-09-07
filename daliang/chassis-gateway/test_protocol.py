"""底盘网关 + 模拟器 的单元测试。

不依赖真机、不依赖网络：在 127.0.0.1:6061 起模拟器，客户端连之。
运行：
    cd suiyue/daliang/chassis-gateway
    python -m unittest test_protocol -v
    # 或：pytest test_protocol.py
"""
from __future__ import annotations

import asyncio
import unittest

import websockets

from daliang_gateway.client import DaliangChassisClient
from daliang_gateway.gateway import ChassisGateway
from daliang_gateway.mock_server import make_handler
from daliang_gateway.world import World


class TestChassisGateway(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.world = World()
        self.server = await websockets.serve(make_handler(self.world), "127.0.0.1", 6061)
        self.events: list = []
        self.client = DaliangChassisClient("ws://127.0.0.1:6061",
                                            on_event=lambda m: self.events.append(m))
        self.gw = ChassisGateway(self.client, upstream_event=lambda m: self.events.append(m))
        await self.gw.start()

    async def asyncTearDown(self) -> None:
        await self.gw.close()
        self.server.close()
        await self.server.wait_closed()

    async def test_status_shape(self) -> None:
        st = await self.client.get_status()
        self.assertEqual(st["robotid"], "TEST1")
        self.assertIn("pos", st)
        self.assertIn("power", st)

    async def test_navigation_arrives(self) -> None:
        await self.client.navigate(2.0, 0.0, speed=1.0)
        await asyncio.sleep(4.0)
        st = await self.client.get_status()
        self.assertAlmostEqual(st["pos"]["x"], 2.0, delta=0.3)
        self.assertEqual(st["goalfinish"], 1)

    async def test_navigation_by_id(self) -> None:
        mid = await self.client.marker_add("0715", "p", "1", -2.0, -1.0)
        r = await self.client.navigate_by_id(mid, speed=1.0)
        self.assertEqual(r["code"], 0)
        await asyncio.sleep(4.0)
        st = await self.client.get_status()
        self.assertAlmostEqual(st["pos"]["x"], -2.0, delta=0.4)

    async def test_patrol_callbacks(self) -> None:
        mid = await self.client.marker_add("0715", "a", "1", 1.0, 0.0)
        await self.client.patrol([{"id": mid, "time": 0}], count=1, speed=1.0)
        await asyncio.sleep(3.0)
        # 经网关翻译后上报为 device_event: patrol_arrive / patrol_depart
        evs = [e.get("event") for e in self.events]
        self.assertTrue(any(ev == "patrol_arrive" for ev in evs), f"无到达回调, events={self.events}")

    async def test_event_nav_then_release(self) -> None:
        await self.client.approach([{"x": 0.5, "y": 0.5, "t": 0, "id": 7, "action": "stop"}])
        await asyncio.sleep(3.0)
        nav_events = [e for e in self.events if e.get("event") == "navigation_event"]
        self.assertTrue(nav_events, "事件导航未暂停上报")
        self.assertEqual(nav_events[0]["id"], 7)
        await self.client.release(7, action_name="stop")
        await asyncio.sleep(2.0)
        self.assertTrue(any(e.get("event") == "event_released" for e in self.events))

    async def test_soft_scram_emits_estop(self) -> None:
        await self.client.stop_all()
        await asyncio.sleep(0.5)
        self.assertTrue(any(e.get("event") == "emergency_stop" for e in self.events))

    async def test_region_set_get(self) -> None:
        poly = [{"x": 1, "y": 1}, {"x": 2, "y": 1}, {"x": 2, "y": 2}]
        await self.client.set_region(1, poly)
        reg = await self.client.get_region()
        regions = reg.get("data", {}).get("regions", [])
        self.assertEqual(len(regions), 1)
        self.assertEqual(regions[0]["id"], 1)

    async def test_mcp_invoke_dispatch(self) -> None:
        # 经网关 invoke 走 MCP 工具分发
        r = await self.gw.invoke("self.daliang.navigate", {"x": 1.5, "y": -1.5, "speed": 1.0})
        self.assertEqual(r["code"], 0)
        await asyncio.sleep(4.0)
        st = await self.client.get_status()
        self.assertAlmostEqual(st["pos"]["y"], -1.5, delta=0.4)

    async def test_unknown_tool(self) -> None:
        with self.assertRaises(ValueError):
            await self.gw.invoke("self.daliang.nope", {})


if __name__ == "__main__":
    unittest.main()
