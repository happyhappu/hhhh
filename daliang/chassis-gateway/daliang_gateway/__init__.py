"""大亮（易行 EGO）底盘网关。

把易行 EGO 底盘的明文 JSON 协议（ws://192.168.31.7:6060 / MQTT :1883）
翻译成 MCP 工具（self.daliang.*），注册到小智云端。

包含：
- protocol  协议常量与响应构造
- world     底盘模拟器的 2D 世界模型（运动学 + 事件调度）
- mock_server 底盘模拟器（WS 服务器，无需真机即可联调）
- client    连底盘（或模拟器）的异步客户端
- gateway   网关：MCP 工具 <-> 底盘命令 的翻译层 + 事件上行
- events    事件 -> MCP-CONTRACT device_event 的格式化
- mcp_tools self.daliang.* 工具清单与分发
"""
from .protocol import (
    ROBOT_WS_URL, RESULT_NAME, ERROR_CODES,
    CMD_GET_STATUS, CMD_NAVIGATION, CMD_NAVIGATION_BY_ID, CMD_NAVIGATION_TYPE,
    CMD_MULTI_POINT_CRUISE, CMD_EVENT_NAVIGATION, CMD_INCIDENT_RELEASE,
    CMD_REMOTE_CONTROL, CMD_SOFT_SCRAM, CMD_CHARGE, CMD_CLEAR_TASK,
    CMD_REGION, CMD_SET_NAV_COLLISION, CMD_GET_LASER, CMD_GET_CAMERA, CMD_MARKER,
    CRUISE_ARRIVE, CRUISE_DEPART, CRUISE_OK,
    build, make_result, parse_outcome,
)
from .world import World
from .client import DaliangChassisClient
from .gateway import ChassisGateway
from .events import patrol_arrive, patrol_depart, navigation_event, emergency_stop, battery_low
from .mcp_tools import TOOLS, handle as mcp_handle

__all__ = [
    "ROBOT_WS_URL", "RESULT_NAME", "ERROR_CODES",
    "CMD_GET_STATUS", "CMD_NAVIGATION", "CMD_NAVIGATION_BY_ID", "CMD_NAVIGATION_TYPE",
    "CMD_MULTI_POINT_CRUISE", "CMD_EVENT_NAVIGATION", "CMD_INCIDENT_RELEASE",
    "CMD_REMOTE_CONTROL", "CMD_SOFT_SCRAM", "CMD_CHARGE", "CMD_CLEAR_TASK",
    "CMD_REGION", "CMD_SET_NAV_COLLISION", "CMD_GET_LASER", "CMD_GET_CAMERA", "CMD_MARKER",
    "CRUISE_ARRIVE", "CRUISE_DEPART", "CRUISE_OK",
    "build", "make_result", "parse_outcome",
    "World", "DaliangChassisClient", "ChassisGateway",
    "patrol_arrive", "patrol_depart", "navigation_event", "emergency_stop", "battery_low",
    "TOOLS", "mcp_handle",
]
