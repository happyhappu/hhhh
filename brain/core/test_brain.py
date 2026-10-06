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
from .provider import DaliangProvider, StaticProvider, is_mobile  # noqa: E402
from .capability import list_models, load_capability  # noqa: E402
from ..daliang_provider.orchestrator import DaliangOrchestrator  # noqa: E402


class TestMobileCapabilityGate(unittest.IsolatedAsyncioTestCase):
    """`is_mobile` 只认 locomotion 字段是否声明，不认具体取值。

    回归防护：曾用 `locomotion == "chassis"` 硬编码，导致 Pepper
    （locomotion: naoqi_wheel）被误判"无移动能力"，approach/navigate/patrol
    全部静默失效——演示"岁悦过来坐坐"时机器人不动且不报错。
    """

    def test_is_mobile_by_presence_not_value(self):
        self.assertTrue(is_mobile({"locomotion": "chassis"}))
        self.assertTrue(is_mobile({"locomotion": "naoqi_wheel"}))
        # 未来新增移动方式无需改 provider.py
        self.assertTrue(is_mobile({"locomotion": "legged"}))
        self.assertTrue(is_mobile({"locomotion": "tracked"}))
        # 桌面本体不可移动
        self.assertFalse(is_mobile({}))
        self.assertFalse(is_mobile({"locomotion": ""}))
        self.assertFalse(is_mobile({"locomotion": None}))

    def test_registry_matches_is_mobile(self):
        """能力注册表与 is_mobile 判定必须一致。"""
        expected = {
            "daliang_v1": True,
            "pepper_v1": True,
            "otto_v1": False,
            "reachy_mini_v1": False,
        }
        for model, want in expected.items():
            with self.subTest(model=model):
                self.assertEqual(is_mobile(load_capability(model)), want)

    async def test_pepper_approach_not_degraded(self):
        """Pepper 是移动本体，approach 必须派发而非降级。"""
        p = StaticProvider("pepper_v1", "pepper-01")
        r = await p.emote({"emotion": "concerned", "intensity": 0.7,
                           "action_primitive": "approach", "params": {"marker_id": "sofa"}})
        self.assertFalse(r.degraded)
        self.assertIsNotNone(r.motion)
        self.assertEqual(r.motion["primitive"], "approach")
        self.assertFalse(r.executed)  # static 仅解析不执行

    async def test_pepper_all_motion_primitives_dispatch(self):
        """Pepper 的移动类原语全部可派发。"""
        p = StaticProvider("pepper_v1", "pepper-01")
        for prim in ("approach", "navigate", "patrol"):
            with self.subTest(primitive=prim):
                r = await p.emote({"emotion": "happy", "intensity": 0.6,
                                   "action_primitive": prim, "params": {}})
                self.assertFalse(r.degraded, f"{prim} 不应被降级")
                self.assertEqual(r.motion["primitive"], prim)

    async def test_desktop_bodies_still_degrade(self):
        """修复不能放宽桌面本体——otto/reachy 仍须静默降级。"""
        for model in ("otto_v1", "reachy_mini_v1"):
            with self.subTest(model=model):
                p = StaticProvider(model, "dev-01")
                r = await p.emote({"emotion": "happy", "intensity": 0.6,
                                   "action_primitive": "approach", "params": {}})
                self.assertTrue(r.degraded)
                self.assertIsNone(r.motion)
                self.assertIn("approach", r.note)


class TestCapabilityRegistryIntegrity(unittest.TestCase):
    """能力注册表结构校验：防止 YAML 手误让安全约束静默失效。"""

    def test_action_lists_are_not_comma_joined_strings(self):
        """动作列表必须是逐项 YAML 序列，不能是单个逗号拼接字符串。

        回归防护：`showcase_only: [hug, dance, push]` 这类流式写法会被解析成
        一个字符串 'hug, dance, push'，导致与 forbidden_actions 的交集为空、
        禁用校验形同虚设。
        """
        for model in list_models():
            cap = load_capability(model)
            for group, items in (cap.get("action_space") or {}).items():
                if not isinstance(items, list):
                    continue
                for it in items:
                    if not isinstance(it, str):
                        continue
                    with self.subTest(model=model, group=group, item=it):
                        self.assertNotIn(
                            ",", it,
                            f"{model}.{group} 的 '{it}' 是逗号拼接的单个字符串，"
                            f"应拆为逐项 YAML 列表（否则与 forbidden_actions 交集为空）")

    def test_forbidden_actions_are_registered(self):
        """forbidden_actions 必须能在 action_space 中找到，否则黑名单是空集。"""
        for model in list_models():
            cap = load_capability(model)
            space = cap.get("action_space") or {}
            registered = set()
            for items in space.values():
                if isinstance(items, list):
                    registered.update(x for x in items if isinstance(x, str))
            forbidden = (cap.get("safety") or {}).get("forbidden_actions") or []
            for act in forbidden:
                with self.subTest(model=model, action=act):
                    self.assertIn(
                        act, registered,
                        f"{model}: forbidden_actions 含未登记动作 '{act}'，黑名单不会生效")

    def test_every_registry_declares_device_model(self):
        for model in list_models():
            with self.subTest(model=model):
                cap = load_capability(model)
                self.assertEqual(cap.get("device_model"), model)



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
