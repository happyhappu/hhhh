"""演示：同一句话，四个身体给出四种不同反应。

运行（在 suiyue/ 根目录）：
    python -m brain.core.demo_four_bodies

无需任何硬件：
- otto / reachy / pepper 用 StaticProvider 模拟固件（按能力注册表解析）；
- daliang 连本仓自带的底盘模拟器（mock server，与真机协议同构）。
"""
from __future__ import annotations

import asyncio
import os
import sys

# 让本模块能 import 兄弟目录的 chassis-gateway 包（目录名含连字符，不能作包名）
_CG = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..",
                                    "daliang", "chassis-gateway"))
if _CG not in sys.path:
    sys.path.insert(0, _CG)

from daliang_gateway.mock_server import make_handler  # noqa: E402
from daliang_gateway.world import World  # noqa: E402
from daliang_gateway.client import DaliangChassisClient  # noqa: E402
from daliang_gateway.gateway import ChassisGateway  # noqa: E402

from .brain import SuiyueBrain  # noqa: E402
from .provider import DaliangProvider  # noqa: E402
from ..daliang_provider.orchestrator import DaliangOrchestrator  # noqa: E402


async def _start_mock_chassis() -> tuple:
    """起一个底盘模拟器，返回 (server, world, port)。"""
    import websockets

    world = World()
    server = await websockets.serve(make_handler(world), "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    return server, world, port


def _print_reactions(title: str, results: dict) -> None:
    print(f"\n=== {title} ===")
    for did, r in results.items():
        flag = " [降级]" if r.degraded else (" [已执行]" if r.executed else "")
        print(f"  • {did} ({r.device_model}){flag}")
        print(f"      表情/姿态: {r.expression}")
        if r.motion:
            print(f"      移动意图: {r.motion}")
        if r.note:
            print(f"      说明:     {r.note}")


async def main() -> None:
    server, world, port = await _start_mock_chassis()

    # 大亮实时提供方：连底盘模拟器
    orch = DaliangOrchestrator()
    client = DaliangChassisClient(url=f"ws://127.0.0.1:{port}")
    orch.gateway = ChassisGateway(client)
    await orch.gateway.start()
    daliang = DaliangProvider(orch, device_id="daliang-01")

    # 预置一个看护点位（用于 approach 演示）
    sofa_id = await orch.invoke_tool("self.daliang.add_marker",
                                     {"map_name": "home", "name": "sofa", "floor": "1",
                                      "x": 1.0, "y": 1.0, "t": 0.0, "mtype": 1})

    brain = SuiyueBrain()
    brain.register("otto-01", "otto_v1")               # 模拟固件
    brain.register("reachy-01", "reachy_mini_v1")      # 模拟固件
    brain.register("daliang-01", "daliang_v1", daliang)  # 实时底盘
    brain.register("pepper-01", "pepper_v1")              # 模拟固件（NAOqi 网关未起时按注册表解析）

    print("注册设备:", brain.device_ids)

    # 场景一：老人讲了个高兴的事 —— 同一句话，四种反应
    intent_happy = {"emotion": "happy", "intensity": 0.8}
    _print_reactions("场景一 · 老人说高兴的事（emotion=happy, intensity=0.8）",
                     await brain.dispatch_emote_all(intent_happy))

    # 场景二：老人情绪低落，需要靠近 —— 显式移动原语
    intent_care = {"emotion": "concerned", "intensity": 0.6,
                   "action_primitive": "approach", "params": {"marker_id": sofa_id}}
    results = await brain.dispatch_emote_all(intent_care)
    _print_reactions("场景二 · 需靠近老人（action_primitive=approach → sofa）", results)
    print(f"\n  大亮底盘当前模式: {world.mode}  （event_nav=走到沙发旁暂停）")

    await orch.close()
    server.close()
    print("\n演示结束。四条本体线在同一意图下给出各自合理的反应，云端零感知差异。")


if __name__ == "__main__":
    asyncio.run(main())
