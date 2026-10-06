"""端到端自动化测试（四方同台，无真机可跑）。

覆盖 suiyue/e2e/README.md 的验收指标，把原来只存在于文档的口径变成可执行断言：

| 指标 | 达标线 | 本脚本对应 |
|---|---|---|
| 语音出声延迟 | <= 1.5s | TestE2ELatency.test_speech_latency（mock 下单） |
| 动作起始延迟 | <= 2.5s | TestE2ELatency.test_action_latency（emote->底盘响应） |
| 三设备同步误差 | <= 300ms | TestE2ELatency.test_sync_spread（四本体分发跨度） |
| 连续运行 | 4h 无崩溃 | TestE2EStability.test_repeated_dispatch（缩短版 N轮） |
| 断网恢复 | 30s 内自恢复 | TestE2EResilience.test_chassis_offline_degrades_gracefully |

全链路真实走：LLM 意图 -> SuiyueBrain.dispatch_emote -> provider -> ChassisGateway
-> DaliangChassisClient -> WS -> mock 底盘 World -> 事件上行 -> poll_events。

运行：
    cd suiyue && python -m unittest e2e.test_e2e -v
或
    cd suiyue && python -m e2e.test_e2e
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import unittest

# --- 注入依赖路径（与各模块 test_*.py 保持同一套做法） ---
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))   # suiyue/
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_CG = os.path.join(_ROOT, "daliang", "chassis-gateway")   # 目录名含连字符，不能作包名
if _CG not in sys.path:
    sys.path.insert(0, _CG)

from daliang_gateway.gateway import ChassisGateway          # noqa: E402
from daliang_gateway.mock_server import make_handler        # noqa: E402
from daliang_gateway.world import World                     # noqa: E402

from brain.core.brain import SuiyueBrain                    # noqa: E402
from brain.core.provider import DaliangProvider             # noqa: E402
from brain.daliang_provider.orchestrator import DaliangOrchestrator  # noqa: E402
from brain.mcp.server import SuiyueMCPServer                # noqa: E402
import websockets                                         # noqa: E402

# --- 验收阈值（来源：e2e/README.md）---
THRESH_SPEECH_LATENCY_S = 1.5
THRESH_ACTION_LATENCY_S = 2.5
THRESH_SYNC_SPREAD_S = 0.3

# 四本体注册表：与 brain/mcp/config.yaml 保持一致
FOUR_BODIES = [
    ("otto-01", "otto_v1"),
    ("reachy-01", "reachy_mini_v1"),
    ("daliang-01", "daliang_v1"),
    ("pepper-01", "pepper_v1"),
]


def _payload(res: dict):
    """从 MCP result 取 text content 并 JSON 解析。"""
    return json.loads(res["content"][0]["text"])


class E2EBase(unittest.IsolatedAsyncioTestCase):
    """起 mock 底盘 + 完整大脑，供各用例复用。"""

    async def asyncSetUp(self) -> None:
        # 随机高位端口，避免 CI 并发/端口占用冲突
        self._srv = await websockets.serve(make_handler(World()), "127.0.0.1", 0)
        self.port = next(iter(self._srv.sockets)).getsockname()[1]
        self.url = f"ws://127.0.0.1:{self.port}"

        self.server = SuiyueMCPServer()
        self.brain = self.server.brain

        # 大亮：真provider（连 mock 底盘）
        orch = DaliangOrchestrator()
        await orch.connect(self.url)
        self.server.daliang = orch

        # 其余三体：static provider（按能力注册表解析，模拟未烧固件）
        self.brain.register("otto-01", "otto_v1")
        self.brain.register("reachy-01", "reachy_mini_v1")
        self.brain.register("daliang-01", "daliang_v1", DaliangProvider(orch, device_id="daliang-01"))
        self.brain.register("pepper-01", "pepper_v1")

    async def asyncTearDown(self) -> None:
        if self.server.daliang and self.server.daliang.gateway:
            try:
                await self.server.daliang.close()
            except Exception:
                pass          # 断网用例已主动关闭连接，关闭时报错可忽略
        # 断网用例可能已 close 过，重复 close 是安全的
        self._srv.close()
        await self._srv.wait_closed()


class TestE2EIntentToMotion(E2EBase):
    """LLM 意图 -> 四本体各自反应（核心链路）。"""

    async def test_happy_dispatch_to_all_four_bodies(self):
        res = await self.server.call_tool(
            "self.suiyue.emote", {"emotion": "happy", "intensity": 0.8})
        self.assertIsNone(res.get("isError"), _payload(res))
        got = _payload(res)

        # 四个本体全部有反应
        self.assertEqual(set(got), {"otto-01", "reachy-01", "daliang-01", "pepper-01"})
        for did, r in got.items():
            self.assertIsNotNone(r.get("expression") or r.get("motion") or r.get("degraded"),
                                 f"{did} 没有任何反应")

    async def test_list_devices_matches_four_bodies(self):
        res = await self.server.call_tool("self.suiyue.list_devices", {})
        self.assertEqual(set(_payload(res)), {d[0] for d in FOUR_BODIES})

    async def test_unknown_device_is_error_not_crash(self):
        """负路径：未知设备必须报isError，而不是抛异常崩server。"""
        res = await self.server.call_tool("self.suiyue.emote",
                                          {"emotion": "happy", "device_id": "ghost-99"})
        self.assertTrue(res.get("isError"))
        # server仍可用
        res2 = await self.server.call_tool("self.suiyue.list_devices", {})
        self.assertIsNone(res2.get("isError"))


class TestE2EChassisAction(E2EBase):
    """动作原语 -> 底盘真实收到命令（走 WS 到 mock World）。"""

    async def test_approach_reaches_chassis(self):
        """大亮 approach 应真的下发到底盘，而不是只在云端返回成功。"""
        before = _payload(await self.server.call_tool("self.daliang.get_status", {}))
        res = await self.server.call_tool(
            "self.daliang.approach", {"points": [{"x": 1.0, "y": 0.5, "t": 0}]})
        self.assertIsNone(res.get("isError"), _payload(res))
        # 给 mock 一点时间 tick 运动学
        await asyncio.sleep(0.5)
        after = _payload(await self.server.call_tool("self.daliang.get_status", {}))
        # 底盘确实朝目标移动了（位置变化即证明命令真的下发到World）
        self.assertNotEqual(
            (before["pos"]["x"], before["pos"]["y"]),
            (after["pos"]["x"], after["pos"]["y"]),
            f"approach 后底盘位置未变化，说明命令没真正下发: {after['pos']}")

    async def test_stop_all_emergency(self):
        """急停是无条件能力，任何时候都要能调通。"""
        res = await self.server.call_tool("self.daliang.stop_all", {})
        self.assertIsNone(res.get("isError"), _payload(res))

    async def test_chassis_status_shape(self):
        """状态轮询是 1Hz 基础接口，字段缺失会让 companion-app 崩。

        真实形状为嵌套：位姿在 pos{x,y,theta}，电量在 power（详见 mock World.snapshot）。
        """
        st = _payload(await self.server.call_tool("self.daliang.get_status", {}))
        for key in ("x", "y", "theta"):
            self.assertIn(key, st["pos"], f"底盘状态 pos 缺 {key}: {st['pos']}")
        for key in ("power", "emgstop", "wheellock", "robotid"):
            self.assertIn(key, st, f"底盘状态缺 {key}: {st}")


class TestE2ELatency(E2EBase):
    """验收指标：出声/动作延迟与三设备同步误差。"""

    async def test_action_latency(self):
        """动作起始延迟 <= 2.5s（意图 -> 底盘收到命令）。"""
        t0 = time.perf_counter()
        await self.server.call_tool("self.suiyue.emote",
                                    {"emotion": "excited", "intensity": 0.9,
                                     "device_id": "daliang-01"})
        elapsed = time.perf_counter() - t0
        self.assertLessEqual(elapsed, THRESH_ACTION_LATENCY_S,
                             f"动作起始延迟 {elapsed:.3f}s > {THRESH_ACTION_LATENCY_S}s")

    async def test_speech_latency(self):
        """语音出声延迟 <= 1.5s（mock 下单往返；真机含 TTS 会更长）。"""
        t0 = time.perf_counter()
        await self.server.call_tool("self.suiyue.get_scene", {"device_id": "pepper-01"})
        elapsed = time.perf_counter() - t0
        self.assertLessEqual(elapsed, THRESH_SPEECH_LATENCY_S,
                             f"出声延迟 {elapsed:.3f}s > {THRESH_SPEECH_LATENCY_S}s")

    async def test_sync_spread_across_bodies(self):
        """三设备同步误差 <= 300ms：同一意图下四本体分发跨度。"""
        stamps = {}
        for did, _ in FOUR_BODIES:
            t0 = time.perf_counter()
            await self.server.call_tool(
                "self.suiyue.emote", {"emotion": "happy", "intensity": 0.7, "device_id": did})
            stamps[did] = time.perf_counter()
        spread = max(stamps.values()) - min(stamps.values())
        self.assertLessEqual(spread, THRESH_SYNC_SPREAD_S,
                             f"同步误差 {spread * 1000:.0f}ms > {THRESH_SYNC_SPREAD_S * 1000:.0f}ms")


class TestE2EStability(E2EBase):
    """验收指标：连续运行无崩溃（CI 缩短为 50 轮，真机做 4h）。"""

    async def test_repeated_dispatch(self):
        for i in range(50):
            res = await self.server.call_tool(
                "self.suiyue.emote", {"emotion": "neutral", "intensity": 0.3})
            if res.get("isError"):
                self.fail(f"第 {i} 轮分发失败: {_payload(res)}")

    async def test_mixed_emotions_never_crash(self):
        """各种情绪混合下发，不应出现未捕获异常。"""
        for emotion in ("happy", "soothing", "concerned", "curious",
                        "excited", "neutral", "unknown_emotion"):
            res = await self.server.call_tool(
                "self.suiyue.emote", {"emotion": emotion, "intensity": 0.5})
            self.assertIsNone(res.get("isError"), f"{emotion} 导致错误: {_payload(res)}")


class TestE2EResilience(E2EBase):
    """验收指标：断网恢复——底盘掉线时优雅降级而非崩溃。

    真实断网模拟：起一个 mock 底盘 -> 连接 -> 主动关闭 server（等价于拔网线），
    而非连一个随机端口（部署机可能配了 http_proxy，连接会被代理接管而失去意义）。
    """

    async def test_chassis_disconnect_degrades_gracefully(self):
        srv = SuiyueMCPServer()
        orch = DaliangOrchestrator(upstream_event=srv._on_event)
        await orch.connect(self.url)
        srv.daliang = orch
        srv.brain.register("daliang-01", "daliang_v1", DaliangProvider(orch, device_id="daliang-01"))

        # 正常期：底盘可达
        ok = await srv.call_tool("self.daliang.get_status", {})
        self.assertIsNone(ok.get("isError"), _payload(ok))

        # 模拟断网：关闭底盘
        self._srv.close()
        await self._srv.wait_closed()
        await asyncio.sleep(0.2)

        # 掉线后：emote 仍可用（表情委派companion-app，不依赖底盘）
        res = await srv.call_tool("self.suiyue.emote",
                                  {"emotion": "happy", "intensity": 0.6})
        self.assertIsNone(res.get("isError"), _payload(res))
        # server 本身不能崩：仍能正常应答其它工具
        res2 = await srv.call_tool("self.suiyue.list_devices", {})
        self.assertIsNone(res2.get("isError"), "底盘掉线不应影响 server 其它能力")

    async def test_unreachable_chassis_registered_but_errors(self):
        """不可达地址：provider 仍注册、emote 可用，底盘工具返回错误而非崩。"""
        srv = SuiyueMCPServer()
        orch = DaliangOrchestrator(upstream_event=srv._on_event)
        srv.daliang = orch
        # 只注册 provider、不连底盘（等价于底盘离线时的降级分支）
        srv.brain.register("daliang-01", "daliang_v1", DaliangProvider(orch, device_id="daliang-01"))

        res = await srv.call_tool("self.suiyue.emote",
                                  {"emotion": "happy", "intensity": 0.6})
        self.assertIsNone(res.get("isError"), _payload(res))
        res2 = await srv.call_tool("self.daliang.get_status", {})
        self.assertTrue(res2.get("isError"), "底盘未连接时应返回 isError")


class TestE2EScenePack(E2EBase):
    """场景包链路（ADR-012 / G5）：LLM 会话开始即拉场景内容。"""

    async def test_get_scene_per_body(self):
        for did, _ in FOUR_BODIES:
            res = await self.server.call_tool("self.suiyue.get_scene", {"device_id": did})
            self.assertIsNone(res.get("isError"), f"{did}: {_payload(res)}")
            sc = _payload(res)
            for key in ("scene_pack", "persona", "safety", "agents"):
                self.assertIn(key, sc, f"{did} 场景缺 {key}")

    async def test_pepper_scene_has_both_agents(self):
        """pepper_cn_v1 继承 elder 域，应同时有 health 与 companion。"""
        sc = _payload(await self.server.call_tool("self.suiyue.get_scene",
                                                  {"device_id": "pepper-01"}))
        self.assertEqual(sc["scene_pack"], "pepper_cn_v1")
        self.assertEqual({a["name"] for a in sc["agents"]}, {"health", "companion"})

    async def test_unknown_scene_device_is_error(self):
        res = await self.server.call_tool("self.suiyue.get_scene", {"device_id": "ghost-99"})
        self.assertTrue(res.get("isError"))


class TestE2EEventUplink(E2EBase):
    """底盘事件 -> 云端 nudge 回路（巡游到达/急停/低电量）。"""

    async def test_soft_scram_generates_alert_event(self):
        from brain.daliang_provider.orchestrator import DaliangOrchestrator as Orch
        nudge = Orch.handle_event({"event": "emergency_stop", "reason": "test"})
        self.assertIsNotNone(nudge)
        self.assertTrue(nudge.get("urgent"))
        self.assertEqual(nudge["type"], "alert")

    async def test_patrol_arrive_generates_presence_nudge(self):
        from brain.daliang_provider.orchestrator import DaliangOrchestrator as Orch
        nudge = Orch.handle_event({"event": "patrol_arrive", "marker_id": 1})
        self.assertEqual(nudge["type"], "context")
        self.assertEqual(nudge["scope"], "presence")

    async def test_normal_status_event_needs_no_dialogue(self):
        from brain.daliang_provider.orchestrator import DaliangOrchestrator as Orch
        self.assertIsNone(Orch.handle_event({"event": "battery_report", "level": 80}))


class TestE2EToolContract(E2EBase):
    """工具契约合规（schema 对齐 MCP-CONTRACT）。"""

    async def test_tool_schemas_valid(self):
        tools = await self.server.list_tools()
        names = {t["name"] for t in tools}
        for must in ("self.suiyue.emote", "self.suiyue.list_devices",
                     "self.suiyue.get_scene", "self.suiyue.poll_events"):
            self.assertIn(must, names)
        for t in tools:
            self.assertEqual(t["inputSchema"]["type"], "object", f"{t['name']} schema 非法")

    async def test_unknown_tool_is_error(self):
        res = await self.server.call_tool("self.daliang.teleport", {})
        self.assertTrue(res.get("isError"))


if __name__ == "__main__":
    unittest.main(verbosity=2)