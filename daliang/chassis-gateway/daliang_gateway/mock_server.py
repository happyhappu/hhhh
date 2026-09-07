"""大亮底盘模拟器（Mock Server）。

无需真机：监听 ws://0.0.0.0:6060，按大亮TCP协议.txt 应答命令，
驱动 World 运动学，并主动上报到达/事件/急停/低电量等事件。

联调真实网关时：把客户端 url 从 ws://localhost:6060 换成 ws://192.168.31.7:6060 即可。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

import websockets

from . import protocol as P
from .world import World

log = logging.getLogger("daliang.mock")


async def _safe_send(ws, msg: dict) -> None:
    try:
        await ws.send(json.dumps(msg, ensure_ascii=False))
    except Exception as e:  # pragma: no cover
        log.warning("event send failed: %s", e)


def dispatch(world: World, msg: dict) -> Optional[dict]:
    """处理一条命令，返回响应字典（事件类命令也返回 ack）。"""
    cmd = msg.get("cmd")
    seq = msg.get("seq", 0)
    data = msg.get("data")
    try:
        if cmd == P.CMD_GET_STATUS or cmd == P.CMD_CONTROL_STATE:
            return P.make_result(cmd, 0, world.snapshot(), seq=seq)

        if cmd == P.CMD_NAVIGATION:
            pts = data or []
            if not pts:
                return P.make_result(cmd, -1, error="empty path", seq=seq)
            world.start_navigation(pts[0])
            return P.make_result(cmd, 0, {"id": pts[0].get("id", -1)}, seq=seq)

        if cmd == P.CMD_NAVIGATION_BY_ID:
            ok = world.start_navigation_by_id(int(data.get("id", -1)))
            if not ok:
                return P.make_result(cmd, -1, error="marker not found", seq=seq)
            return P.make_result(cmd, 0, {"id": data.get("id")}, seq=seq)

        if cmd == P.CMD_MULTI_POINT_CRUISE:
            d = data or {}
            world.start_cruise(d.get("points", []), d.get("count", 1),
                               float(d.get("speed", 0.7)), d.get("type", 1))
            return P.make_result(cmd, 0, "Cruise started successfully", seq=seq)

        if cmd == P.CMD_EVENT_NAVIGATION:
            world.start_event_nav(data or [])
            return P.make_result(cmd, 0, seq=seq)

        if cmd == P.CMD_INCIDENT_RELEASE:
            world.release_event(msg.get("id"), msg.get("actionName", ""))
            return P.make_result(cmd, 0, seq=seq)

        if cmd == P.CMD_REMOTE_CONTROL:
            world.remote_control(float(msg.get("x", 0)), float(msg.get("y", 0)), float(msg.get("t", 0)))
            return P.make_result(cmd, 0, seq=seq)

        if cmd == P.CMD_SOFT_SCRAM:
            world.soft_scram(bool(data))
            return P.make_result(cmd, 0, seq=seq)

        if cmd == P.CMD_CHARGE:
            world.set_charge(bool(msg.get("value", False)))
            return P.make_result(cmd, 0, seq=seq)

        if cmd == P.CMD_CLEAR_TASK:
            world.clear_task()
            return P.make_result(cmd, 0, seq=seq)

        if cmd == P.CMD_REGION:
            command = msg.get("command")
            if command == "get":
                return P.make_result(cmd, 0, {"regions": world.get_regions()}, seq=seq)
            if command == "set":
                d = data or {}
                world.set_region(int(d.get("id", 0)), d.get("data", []))
                return P.make_result(cmd, 0, seq=seq)
            return P.make_result(cmd, -1, error="unknown region command", seq=seq)

        if cmd == P.CMD_SET_NAV_COLLISION:
            world.set_nav_collision(int(data or 0))
            return P.make_result(cmd, 0, seq=seq)

        if cmd in (P.CMD_GET_LASER, P.CMD_GET_POSITIONING_LASER):
            return P.make_result(cmd, 0, world.fake_laser(), seq=seq)

        if cmd == P.CMD_GET_CAMERA:
            return P.make_result(cmd, 0, world.fake_camera(), seq=seq)

        if cmd == P.CMD_MARKER:
            return dispatch_marker(world, msg, seq)

        return P.make_result(cmd or "?", -1, error="unknown cmd", seq=seq)

    except Exception as e:  # pragma: no cover
        log.exception("dispatch error")
        return P.make_result(cmd or "?", -1, error=str(e), seq=seq)


def dispatch_marker(world: World, msg: dict, seq: int) -> dict:
    command = msg.get("command")
    data = msg.get("data") or {}
    if command == "getAll" or command == "getMapAll":
        return P.make_result(P.CMD_MARKER, 0, {"markers": world.marker_get_all()}, seq=seq)
    if command == "add":
        mid = world.marker_add(data.get("mapName", P.DEFAULT_MAP), data.get("name", ""),
                               data.get("floor", "1"), float(data.get("x", 0)), float(data.get("y", 0)),
                               float(data.get("t", 0)), int(data.get("type", 1)))
        return P.make_result(P.CMD_MARKER, 0, {"id": mid}, seq=seq)
    if command == "del":
        world.marker_del(int(data.get("id", -1)))
        return P.make_result(P.CMD_MARKER, 0, seq=seq)
    if command == "delFind":
        return P.make_result(P.CMD_MARKER, 0, seq=seq)
    if command == "update":
        return P.make_result(P.CMD_MARKER, 0, seq=seq)
    if command == "clear":
        world.marker_clear()
        return P.make_result(P.CMD_MARKER, 0, seq=seq)
    return P.make_result(P.CMD_MARKER, -1, error="unknown marker command", seq=seq)


async def handler(world: World, ws, *args) -> None:
    loop = asyncio.get_event_loop()
    world.on_event = lambda ev: asyncio.ensure_future(_safe_send(ws, ev))

    async def tick_loop() -> None:
        while True:
            world.tick(0.1)
            await asyncio.sleep(0.1)

    tick_task = asyncio.ensure_future(tick_loop())
    try:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except Exception:
                await _safe_send(ws, P.make_result("_", -1, error="bad json"))
                continue
            resp = dispatch(world, msg)
            if resp is not None:
                await _safe_send(ws, resp)
    finally:
        tick_task.cancel()
        try:
            await tick_task
        except (asyncio.CancelledError, Exception):  # pragma: no cover
            pass


def make_handler(world: World):
    """返回 websockets.serve 可用的 handler（兼容 path 参数）。"""
    return lambda ws, *a: handler(world, ws, *a)


async def start_mock(world: Optional[World] = None, host: str = "0.0.0.0", port: int = 6060):
    """启动模拟器，返回 server 对象。"""
    world = world or World()
    server = await websockets.serve(make_handler(world), host, port)
    log.info("大亮底盘模拟器已启动 ws://%s:%d", host, port)
    return server, world


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_run_forever())


async def _run_forever() -> None:
    server, _ = await start_mock()
    await server.wait_closed()


if __name__ == "__main__":
    main()
