"""连大亮底盘（或模拟器）的异步客户端。

请求/响应按 seq 关联；设备主动上报（巡游到达回调、事件导航、急停、低电量）走 on_event。
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Optional

import websockets

from . import protocol as P

log = logging.getLogger("daliang.client")


class DaliangChassisClient:
    def __init__(self, url: str = P.ROBOT_WS_URL, on_event: Optional[Callable[[dict, ], None]] = None):
        self.url = url
        self.on_event = on_event
        self.ws = None
        self._seq = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        # 底盘是内网/局域网地址，绝不能走 HTTP 代理。
        # websockets>=14 的connect() 默认读环境变量 http_proxy/https_proxy，
        # 若部署机设了代理（机房/企业网常见）而 no_proxy 未覆盖内网网段，
        # 连接会被代理接管并以 502 失败 —— 这对"100% 内网离线部署"是硬伤。
        # 故显式 proxy=None；旧版 websockets 无该参数则退回默认调用。
        try:
            self.ws = await websockets.connect(self.url, proxy=None)
        except TypeError:
            self.ws = await websockets.connect(self.url)
        self._task = asyncio.ensure_future(self._recv())

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
        if self.ws is not None:
            await self.ws.close()

    async def _recv(self) -> None:
        assert self.ws is not None
        async for raw in self.ws:
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            seq = msg.get("seq", 0)
            if seq in self._pending:
                self._pending[seq].set_result(msg)
                continue
            if self.on_event:
                self.on_event(msg)

    async def _request(self, cmd: str, fields: Optional[dict] = None, timeout: float = 5.0) -> dict:
        assert self.ws is not None
        self._seq += 1
        seq = self._seq
        msg: dict = {"cmd": cmd, "seq": seq}
        if fields:
            msg.update(fields)
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[seq] = fut
        await self.ws.send(json.dumps(msg, ensure_ascii=False))
        try:
            return await asyncio.wait_for(fut, timeout)
        finally:
            self._pending.pop(seq, None)

    # ---------------- 高层命令 ----------------
    async def get_status(self) -> dict:
        r = await self._request(P.CMD_GET_STATUS)
        return r.get("data", {})

    async def navigate(self, x: float, y: float, theta: float = 0.0, speed: float = 0.7,
                       point_id: int = -1) -> dict:
        return await self._request(P.CMD_NAVIGATION,
                                   {"data": [{"id": point_id, "x": x, "y": y, "t": theta, "speed": speed}]})

    async def navigate_by_id(self, marker_id: int, speed: float = 0.7, nav_type: int = 1) -> dict:
        return await self._request(P.CMD_NAVIGATION_BY_ID,
                                   {"data": {"id": marker_id, "speed": speed, "type": nav_type}})

    async def patrol(self, points: list, count: int = 1, speed: float = 0.7, nav_type: int = 1) -> dict:
        return await self._request(P.CMD_MULTI_POINT_CRUISE,
                                   {"data": {"points": points, "count": count, "speed": speed, "type": nav_type}})

    async def approach(self, points: list, auto_nav: int = 1) -> dict:
        """走到点位并暂停，等 release 释放（"走到老人身边说话"）。"""
        return await self._request(P.CMD_EVENT_NAVIGATION, {"autoNav": auto_nav, "data": points})

    async def release(self, event_id: int, action_name: str = "") -> dict:
        return await self._request(P.CMD_INCIDENT_RELEASE, {"id": event_id, "actionName": action_name})

    async def follow(self, x: float = 0.0, y: float = 0.0, t: float = 0.0) -> dict:
        return await self._request(P.CMD_REMOTE_CONTROL, {"x": x, "y": y, "t": t})

    async def stop_all(self) -> dict:
        return await self._request(P.CMD_SOFT_SCRAM, {"data": True})

    async def release_stop(self) -> dict:
        return await self._request(P.CMD_SOFT_SCRAM, {"data": False})

    async def dock(self, go: bool = True) -> dict:
        return await self._request(P.CMD_CHARGE, {"value": go})

    async def clear_task(self) -> dict:
        return await self._request(P.CMD_CLEAR_TASK)

    async def set_region(self, region_id: int, polygon: list) -> dict:
        return await self._request(P.CMD_REGION, {"command": "set", "data": {"id": region_id, "data": polygon}})

    async def get_region(self) -> dict:
        return await self._request(P.CMD_REGION, {"command": "get"})

    async def set_nav_collision(self, mode: int = 0) -> dict:
        return await self._request(P.CMD_SET_NAV_COLLISION, {"data": mode})

    async def get_laser(self) -> dict:
        r = await self._request(P.CMD_GET_LASER)
        return r.get("data", {})

    async def get_camera(self) -> dict:
        r = await self._request(P.CMD_GET_CAMERA)
        return r.get("data", {})

    async def marker_add(self, map_name: str, name: str, floor: str,
                         x: float, y: float, t: float = 0.0, mtype: int = 1) -> int:
        r = await self._request(P.CMD_MARKER,
                                {"command": "add",
                                 "data": {"mapName": map_name, "name": name, "floor": floor,
                                          "x": x, "y": y, "t": t, "type": mtype}})
        return r.get("data", {}).get("id")

    async def marker_get_all(self) -> dict:
        return await self._request(P.CMD_MARKER, {"command": "getAll"})

    async def marker_del(self, marker_id: int) -> dict:
        return await self._request(P.CMD_MARKER, {"command": "del", "data": {"id": marker_id}})

    async def marker_clear(self) -> dict:
        return await self._request(P.CMD_MARKER, {"command": "clear"})
