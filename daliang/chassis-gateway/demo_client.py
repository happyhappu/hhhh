"""演示：启动底盘模拟器 + 跑一遍 self.daliang.* 全流程。

运行：
    cd suiyue/daliang/chassis-gateway
    python demo_client.py

会自动起一个 ws://localhost:6060 的模拟器，演示：
1) 取状态  2) 加标记点  3) 自由导航  4) 多点巡游（带到达回调）
5) 事件导航（走到身边暂停）-> 释放  6) 软急停  7) 虚拟墙  8) 回桩
"""
from __future__ import annotations

import asyncio
import logging

from daliang_gateway.client import DaliangChassisClient
from daliang_gateway.gateway import ChassisGateway
from daliang_gateway.mock_server import start_mock
from daliang_gateway.world import World

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
log = logging.getLogger("demo")


async def main() -> None:
    world = World()
    server, _ = await start_mock(world, host="127.0.0.1", port=6060)

    events: list = []

    def on_event(ev: dict) -> None:
        events.append(ev)
        log.info("事件上行 -> %s", ev)

    client = DaliangChassisClient("ws://127.0.0.1:6060", on_event=on_event)
    gw = ChassisGateway(client, upstream_event=on_event)
    await gw.start()
    log.info("=== 1) 取状态 ===")
    st = await client.get_status()
    log.info("robotid=%s pos=(%.2f,%.2f) power=%.1f", st["robotid"], st["pos"]["x"], st["pos"]["y"], st["power"])

    log.info("=== 2) 加标记点（沙发 / 餐桌）===")
    sofa = await client.marker_add("0715", "sofa", "1", 1.0, 1.0)
    table = await client.marker_add("0715", "table", "1", -1.5, 0.5)
    log.info("marker sofa id=%s, table id=%s", sofa, table)

    log.info("=== 3) 自由导航到 (2.0, 0.0) ===")
    await client.navigate(2.0, 0.0, theta=0.0, speed=0.7)
    await asyncio.sleep(4.0)
    st = await client.get_status()
    log.info("到达后 pos=(%.2f,%.2f) goalfinish=%s", st["pos"]["x"], st["pos"]["y"], st["goalfinish"])

    log.info("=== 4) 多点巡游（餐桌停留4s -> 沙发不停）===")
    await client.patrol(
        [{"id": table, "time": 4}, {"id": sofa, "time": 0}],
        count=1, speed=0.7,
    )
    await asyncio.sleep(12.0)

    log.info("=== 5) 事件导航：走到 (0.3,0.3) 暂停，等释放 ===")
    await client.approach([{"x": 0.3, "y": 0.3, "t": 0, "id": 99, "action": "stop"}])
    await asyncio.sleep(4.0)
    log.info("释放事件 99")
    await client.release(99, action_name="stop")
    await asyncio.sleep(3.0)

    log.info("=== 6) 软急停 ===")
    await client.stop_all()
    await asyncio.sleep(1.0)

    log.info("=== 7) 虚拟墙（卧室禁入）===")
    await client.set_region(1, [{"x": 3.0, "y": 3.0}, {"x": 5.0, "y": 3.0}, {"x": 5.0, "y": 5.0}, {"x": 3.0, "y": 5.0}])
    reg = await client.get_region()
    log.info("regions=%s", reg.get("data", {}).get("regions"))

    log.info("=== 8) 回桩充电 ===")
    await client.dock(go=True)
    await asyncio.sleep(1.0)

    log.info("=== 演示结束，共收集 %d 条上行事件 ===", len(events))
    await gw.close()
    server.close()
    await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
