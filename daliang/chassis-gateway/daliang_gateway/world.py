"""底盘模拟器的 2D 世界模型。

负责：位姿/电量/导航状态、运动学积分、到达事件与巡游/事件导航调度、
虚拟墙与标记点管理、激光/相机（深度）数据仿真。

纯逻辑、无网络。mock_server 每 100ms 调一次 tick()，把世界状态推给 WS 客户端。
"""
from __future__ import annotations

import math
from typing import Any, Callable, Optional

from . import protocol as P


class World:
    def __init__(self, map_name: str = P.DEFAULT_MAP, robot_id: str = P.DEFAULT_ROBOT_ID):
        # 位姿
        self.map_name = map_name
        self.robot_id = robot_id
        self.x = 0.0
        self.y = 0.0
        self.theta = 0.0
        # 当前速度指令（m/s, rad/s）
        self.vx = 0.0
        self.vy = 0.0
        self.omega = 0.0
        # 电量
        self.power = 82.0
        self.charging = False
        self._lowflag = False
        # 导航状态
        self.mode = "idle"            # idle / moving / patrol / event_nav / event_hold / remote / charging
        self.target: Optional[dict] = None
        self.speed = 0.7
        self.cruise: Optional[dict] = None
        self.event_queue: list = []
        self.event_hold: Optional[dict] = None
        # 状态标志
        self.softpause = False
        self.wheellock = False
        self.emgstop = False
        self.collision_mode = 0
        self.collision_warning = False
        # 地图要素
        self.markers: dict[int, dict] = {}     # id -> marker
        self.regions: list[dict] = []
        self._marker_seq = 1
        # 上报
        self.currentglobalid = -1
        self.goalfinish = P.GOAL_IDLE
        self.errcode = 0
        # 事件回调
        self.on_event: Optional[Callable[[dict], None]] = None

    # ---------------- 事件 ----------------
    def _emit(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

    def _emit_mcp(self, event: str, **kw: Any) -> None:
        self._emit({"type": "device_event", "event": event, **kw})

    # ---------------- 运动学 ----------------
    def tick(self, dt: float) -> None:
        if self.emgstop or self.softpause or self.wheellock:
            self.vx = self.vy = self.omega = 0.0
            return
        if self.mode == "remote":
            self._integrate(dt)
        elif self.mode == "patrol" and self.cruise and self.cruise.get("state") == "dwell":
            self.cruise["dwell"] -= dt
            if self.cruise["dwell"] <= 0:
                self._cruise_next()
        elif self.mode in ("moving", "patrol", "event_nav"):
            self._step_to_target(dt)
        # 电量
        if self.charging:
            self.power = min(100.0, self.power + 0.8 * dt)
        elif self.mode in ("moving", "patrol", "event_nav", "remote"):
            self.power = max(0.0, self.power - 0.02 * dt)
        if self.power <= 15.0 and not self._lowflag:
            self._lowflag = True
            self._emit_mcp("battery_low", level=int(self.power))
        if self.power > 20.0:
            self._lowflag = False

    def _integrate(self, dt: float) -> None:
        self.x += self.vx * math.cos(self.theta) * dt
        self.y += self.vx * math.sin(self.theta) * dt
        self.theta += self.omega * dt

    def _set_target_from_point(self, p: dict) -> None:
        self.target = {
            "x": float(p["x"]),
            "y": float(p["y"]),
            "theta": float(p.get("t", p.get("theta", 0.0))),
            "id": p.get("id", -1),
        }
        self.speed = float(p.get("speed", self.speed))

    def _step_to_target(self, dt: float) -> None:
        tgt = self.target
        if tgt is None:
            return
        dx = tgt["x"] - self.x
        dy = tgt["y"] - self.y
        dist = math.hypot(dx, dy)
        if dist > 0.05:
            ang = math.atan2(dy, dx)
            self.theta = ang
            self.x += math.cos(ang) * self.speed * dt
            self.y += math.sin(ang) * self.speed * dt
            self.vx = self.speed
            self.omega = 0.0
        else:
            dth = tgt["theta"] - self.theta
            if abs(dth) > 0.03:
                step = 0.6 * dt
                self.theta += math.copysign(min(abs(dth), step), dth)
                self.omega = 0.6
            else:
                self.theta = tgt["theta"]
                self._arrive()

    def _arrive(self) -> None:
        self.vx = self.vy = self.omega = 0.0
        if self.mode == "patrol" and self.cruise:
            p = self.cruise["points"][self.cruise["idx"]]
            self._emit({"cmd": "multiPointCruise_result", "code": P.CRUISE_ARRIVE, "data": p.get("id")})
            self.cruise["state"] = "dwell"
            self.cruise["dwell"] = float(p.get("time", 0) or 0.0)
            self.goalfinish = P.GOAL_RUNNING
        elif self.mode == "event_nav" and self.event_queue:
            p = self.event_queue[0]
            self.event_hold = p
            self.mode = "event_hold"
            self._emit_mcp("navigation_event", id=p.get("id"), action=p.get("action", ""))
        else:
            self.mode = "idle"
            self.goalfinish = P.GOAL_DONE
            self.currentglobalid = self.target.get("id", -1) if self.target else -1
            self._emit_mcp("goal_reached", x=round(self.x, 3), y=round(self.y, 3))

    def _cruise_next(self) -> None:
        c = self.cruise
        c["idx"] += 1
        if c["idx"] >= len(c["points"]):
            c["loop"] += 1
            if c["loop"] >= c["count"]:
                self._emit({"cmd": "multiPointCruise_result", "code": P.CRUISE_OK, "data": "cruise finished"})
                self.cruise = None
                self.mode = "idle"
                self.goalfinish = P.GOAL_DONE
                self.target = None
                return
            c["idx"] = 0
        p = c["points"][c["idx"]]
        self._set_target_from_point(p)
        self.mode = "patrol"
        c["state"] = "moving"
        self._emit({"cmd": "multiPointCruise_result", "code": P.CRUISE_DEPART, "data": p.get("id")})

    # ---------------- 命令实现 ----------------
    def start_navigation(self, p: dict) -> None:
        self._set_target_from_point(p)
        self.mode = "moving"
        self.goalfinish = P.GOAL_RUNNING

    def start_navigation_by_id(self, marker_id: int) -> bool:
        m = self.markers.get(marker_id)
        if not m:
            return False
        self._set_target_from_point(m)
        self.mode = "moving"
        self.goalfinish = P.GOAL_RUNNING
        return True

    def start_cruise(self, points: list, count: int, speed: float, nav_type: int) -> None:
        """points 可按 x/y 直接给，也可按 marker id 引用（协议文档即 id+time）。"""
        resolved = []
        for p in points:
            if "x" in p and "y" in p:
                item = dict(p)
            else:
                m = self.markers.get(int(p.get("id", -1)))
                if not m:
                    raise ValueError(f"marker {p.get('id')} not found")
                item = {"id": p.get("id"), "x": m["x"], "y": m["y"],
                        "t": m.get("t", 0.0), "speed": speed, "time": p.get("time", 0)}
            resolved.append(item)
        if not resolved:
            raise ValueError("no cruise points")
        self.cruise = {
            "points": resolved,
            "count": count if count and count > 0 else 1,
            "speed": speed,
            "type": nav_type,
            "idx": 0,
            "loop": 0,
            "state": "moving",
            "dwell": 0.0,
        }
        self.mode = "patrol"
        self.goalfinish = P.GOAL_RUNNING
        self._set_target_from_point(self.cruise["points"][0])
        self._emit({"cmd": "multiPointCruise_result", "code": P.CRUISE_DEPART, "data": self.cruise["points"][0].get("id")})

    def start_event_nav(self, points: list) -> None:
        self.event_queue = list(points)
        self.mode = "event_nav"
        self.goalfinish = P.GOAL_RUNNING
        self._set_target_from_point(self.event_queue[0])

    def release_event(self, event_id: int, action_name: str) -> None:
        if self.mode == "event_hold" and self.event_hold and self.event_hold.get("id") == event_id:
            self.event_queue.pop(0)
            self.event_hold = None
            if self.event_queue:
                self._set_target_from_point(self.event_queue[0])
                self.mode = "event_nav"
            else:
                self.mode = "idle"
                self.goalfinish = P.GOAL_DONE
                self.target = None
            self._emit_mcp("event_released", id=event_id, action=action_name)

    def remote_control(self, x: float, y: float, t: float) -> None:
        self.mode = "remote"
        self.vx = x
        self.vy = y
        self.omega = t
        self.target = None

    def soft_scram(self, lock: bool) -> None:
        self.softpause = bool(lock)
        self.wheellock = bool(lock)
        if lock:
            self.vx = self.vy = self.omega = 0.0
            self._emit_mcp("emergency_stop", reason="soft_scram")

    def set_charge(self, go: bool) -> None:
        if go:
            self.mode = "charging"
            self.charging = True
        else:
            self.charging = False
            self.mode = "idle"

    def clear_task(self) -> None:
        self.cruise = None
        self.event_queue = []
        self.event_hold = None
        self.target = None
        self.mode = "idle"
        self.goalfinish = P.GOAL_IDLE
        self.vx = self.vy = self.omega = 0.0

    def set_region(self, region_id: int, polygon: list) -> None:
        self.regions = [r for r in self.regions if r["id"] != region_id]
        self.regions.append({"id": region_id, "data": polygon})

    def get_regions(self) -> list:
        return [r for r in self.regions]

    def set_nav_collision(self, mode: int) -> None:
        self.collision_mode = int(mode)

    # ---------------- 标记点 ----------------
    def marker_add(self, map_name: str, name: str, floor: str,
                   x: float, y: float, t: float = 0.0, mtype: int = 1) -> int:
        mid = self._marker_seq
        self._marker_seq += 1
        self.markers[mid] = {
            "id": mid, "name": name, "floor": floor,
            "x": x, "y": y, "t": t, "type": mtype, "mapName": map_name,
        }
        return mid

    def marker_get_all(self) -> list:
        return [dict(m) for m in self.markers.values()]

    def marker_del(self, marker_id: int) -> None:
        self.markers.pop(marker_id, None)

    def marker_clear(self) -> None:
        self.markers.clear()

    # ---------------- 传感器仿真 ----------------
    def fake_laser(self) -> dict:
        """仿真 30m 激光（与文档 subscriptionLaser_result 同构）。"""
        n = 120
        inc = (2 * 2.3562) / n
        scan = [30000] * n
        # 放两个障碍
        for i in (30, 95):
            scan[i] = 1800
        return {
            "angle_max": 2.3562, "angle_start": -2.3562, "direction": "increase",
            "increment": inc, "name": "scan", "rame_id": "/laser_link",
            "range_max": 30, "range_min": 0.05, "scan": scan,
        }

    def fake_camera(self) -> dict:
        """仿真相机数据：注意是【深度点云】，不是 RGB 图像帧（与文档一致）。"""
        scan = [60000] * 60  # 60000 = 无返回
        return {"name": "depth", "range_max": 30, "range_min": 0.05, "scan": scan}

    # ---------------- 状态快照 ----------------
    def snapshot(self) -> dict:
        return {
            "agvSpeed": {"t": self.omega, "x": self.vx},
            "agvStop": 103 if self.mode == "moving" else 100,
            "chargestatu": {
                "state": 100 if self.charging else -1,
                "pos": {"mapname": self.map_name, "x": round(self.x, 4), "y": round(self.y, 4)},
                "powerquantity": int(self.power),
            },
            "chargestep": -1,
            "collisionwarning": self.collision_warning,
            "currentBv": -1,
            "currentFv": -1,
            "currentglobalid": self.currentglobalid,
            "emgstop": self.emgstop,
            "errcode": self.errcode,
            "errorcode": [],
            "goalfinish": self.goalfinish,
            "inmanualcharge": -1,
            "innavmap": True,
            "inbuildmap": False,
            "issoftpause": self.softpause,
            "odomhz": 82.0,
            "pos": {
                "mapname": self.map_name,
                "theta": round(self.theta, 4),
                "x": round(self.x, 4),
                "y": round(self.y, 4),
                "z": round(self.theta, 4),
            },
            "pose_probability": 0.95,
            "power": round(self.power, 2),
            "powerquantity": int(self.power),
            "robotid": self.robot_id,
            "scanhz": 15.0,
            "version": "mock-1.0",
            "wheellock": self.wheellock,
        }
