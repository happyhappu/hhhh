"""大亮 EGO 底盘协议常量与消息构造。

依据：大亮TCP协议.txt（63 页全文提取）。
传输：ws://192.168.31.7:6060（机器人作服务器，明文 JSON）；
      MQTT 192.168.31.7:1883（发布 server/api / 订阅 client/data）；
      HTTP 192.168.31.7:9999（table / route，本网关暂不涉及）。

本模块只负责【构造请求】与【解析响应】，不负责网络传输。
"""
from __future__ import annotations

import json
from typing import Any, Optional

# ---- 端点（真机固定内网地址；模拟器改用 localhost）----
ROBOT_WS_URL = "ws://192.168.31.7:6060"
ROBOT_HTTP_URL = "http://192.168.31.7:9999"
ROBOT_MQTT = "192.168.31.7:1883"

# ---- 命令名 ----
CMD_GET_STATUS = "getAgvStatus"
CMD_CONTROL_STATE = "getControlState"
CMD_NAVIGATION = "navigation"
CMD_NAVIGATION_BY_ID = "navigationById"
CMD_NAVIGATION_TYPE = "navigationType"
CMD_MULTI_POINT_CRUISE = "multiPointCruise"
CMD_EVENT_NAVIGATION = "eventNavigation"
CMD_INCIDENT_RELEASE = "incidentRelease"
CMD_REMOTE_CONTROL = "remoteControl"
CMD_SOFT_SCRAM = "softScram"
CMD_CHARGE = "charge"
CMD_CLEAR_TASK = "clearTask"
CMD_REGION = "region"
CMD_SET_NAV_COLLISION = "setNavCollisionMode"
CMD_GET_LASER = "getLaser"
CMD_GET_POSITIONING_LASER = "getPositioningLaser"
CMD_GET_CAMERA = "getCamera"
CMD_MARKER = "marker"

# ---- 多点巡航回调码（设备主动上报，非请求应答）----
CRUISE_DEPART = 1001   # 出发前往某点，data=点位 id
CRUISE_ARRIVE = 1000   # 到达某点，data=点位 id
CRUISE_OK = 0          # 启动成功 / 全部结束，data=提示串

# ---- goalfinish（导航状态）----
GOAL_IDLE = -2
GOAL_RUNNING = 0
GOAL_DONE = 1
GOAL_FAILED = -1

# ---- 响应命令名映射（与请求名并非简单加 _result）----
# 文档实测：getAgvStatus -> agvStatus_result；getLaser -> subscriptionLaser_result；
# getCamera -> subscriptionCamera_result；navigationById/navigationType -> navigation_result。
RESULT_NAME = {
    CMD_GET_STATUS: "agvStatus_result",
    CMD_CONTROL_STATE: "controlState_result",
    CMD_GET_LASER: "subscriptionLaser_result",
    CMD_GET_POSITIONING_LASER: "subscriptionLaser_result",
    CMD_GET_CAMERA: "subscriptionCamera_result",
    CMD_NAVIGATION: "navigation_result",
    CMD_NAVIGATION_BY_ID: "navigation_result",
    CMD_NAVIGATION_TYPE: "navigation_result",
}


def result_cmd(req_cmd: str) -> str:
    """请求命令 -> 响应命令名。"""
    return RESULT_NAME.get(req_cmd, f"{req_cmd}_result")


# ---- 错误码（文档 10000-60000，摘常用）----
ERROR_CODES = {
    10000: "未知错误",
    20000: "导航目标点无效",
    20001: "未进入地图/未定位",
    30000: "急停触发",
    40000: "防撞触发",
    50000: "电量过低",
    60000: "通信超时",
}

DEFAULT_MAP = "0715"
DEFAULT_ROBOT_ID = "TEST1"


def build(cmd: str, seq: int = 0, **fields: Any) -> str:
    """构造一条底盘命令的 JSON 文本。

    fields 直接铺在顶层（如 remoteControl 的 x/y/t、charge 的 value、
    incidentRelease 的 id/actionName、region 的 command、marker 的 command…）。
    data 类字段通过 data=... 传入。
    """
    msg: dict = {"cmd": cmd, "seq": seq}
    msg.update(fields)
    return json.dumps(msg, ensure_ascii=False)


# ---- 常用命令构造器 ----
def cmd_get_status(seq: int = 0) -> str:
    return build(CMD_GET_STATUS, seq)


def cmd_navigation(point: dict, seq: int = 0) -> str:
    """point: {id, x, y, t, speed}。"""
    return build(CMD_NAVIGATION, seq, data=[point])


def cmd_navigation_by_id(marker_id: int, speed: float = 0.7, nav_type: int = 1, seq: int = 0) -> str:
    return build(CMD_NAVIGATION_BY_ID, seq, data={"id": marker_id, "speed": speed, "type": nav_type})


def cmd_multi_point_cruise(points: list, count: int = 1, speed: float = 0.7,
                            nav_type: int = 1, seq: int = 0) -> str:
    return build(CMD_MULTI_POINT_CRUISE, seq,
                 data={"points": points, "count": count, "speed": speed, "type": nav_type})


def cmd_event_navigation(points: list, auto_nav: int = 1, seq: int = 0) -> str:
    return build(CMD_EVENT_NAVIGATION, seq, autoNav=auto_nav, data=points)


def cmd_incident_release(event_id: int, action_name: str = "", seq: int = 0) -> str:
    return build(CMD_INCIDENT_RELEASE, seq, id=event_id, actionName=action_name)


def cmd_remote_control(x: float = 0.0, y: float = 0.0, t: float = 0.0, seq: int = 0) -> str:
    return build(CMD_REMOTE_CONTROL, seq, x=x, y=y, t=t)


def cmd_soft_scram(lock: bool, seq: int = 0) -> str:
    return build(CMD_SOFT_SCRAM, seq, data=lock)


def cmd_charge(go: bool, seq: int = 0) -> str:
    return build(CMD_CHARGE, seq, value=go)


def cmd_clear_task(seq: int = 0) -> str:
    return build(CMD_CLEAR_TASK, seq)


def cmd_region_get(seq: int = 0) -> str:
    return build(CMD_REGION, seq, command="get")


def cmd_region_set(region_id: int, polygon: list, seq: int = 0) -> str:
    return build(CMD_REGION, seq, command="set", data={"id": region_id, "data": polygon})


def cmd_set_nav_collision(mode: int = 0, seq: int = 0) -> str:
    return build(CMD_SET_NAV_COLLISION, seq, data=mode)


def cmd_get_laser(seq: int = 0) -> str:
    return build(CMD_GET_LASER, seq)


def cmd_get_camera(seq: int = 0) -> str:
    return build(CMD_GET_CAMERA, seq)


def cmd_marker(command: str, data: Optional[dict] = None, seq: int = 0) -> str:
    if data is not None:
        return build(CMD_MARKER, seq, command=command, data=data)
    return build(CMD_MARKER, seq, command=command)


def make_result(req_cmd: str, code: int = 0, data: Any = None,
                error: Optional[str] = None, seq: int = 0) -> dict:
    """标准响应信封（文档表 2-1）：{cmd, code, [error], [data], seq}。"""
    r: dict = {"cmd": result_cmd(req_cmd), "code": code, "seq": seq}
    if error is not None:
        r["error"] = error
    if data is not None:
        r["data"] = data
    return r


def parse_outcome(result: dict) -> tuple[bool, int, Optional[str], Any]:
    """(ok, code, error, data)。"""
    code = result.get("code", -1)
    return (code == 0, code, result.get("error"), result.get("data"))
