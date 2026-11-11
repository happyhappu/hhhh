# -*- coding: utf-8 -*-
"""
naoqi_bridge 全局配置常量。

同时兼容 Python 2.7 与 3.x（本桥运行时必须用 Py2.7；测试/校验可用 Py3）。
"""
from __future__ import print_function, absolute_import

# ---- 连接 ----
DEFAULT_QI_URL = "tcp://192.168.0.93:9559"   # Pepper NAOqi broker
DEFAULT_IPC_HOST = "127.0.0.1"               # 主网关 ↔ 桥 本地 IPC
DEFAULT_IPC_PORT = 9560

# ---- 音频（麦克风上云入口，参照 NAOqi 2.5 培训文档 2-3 节）----
AUDIO_CLIENT_NAME = "pepper_bridge_audio"    # 注册到 ALAudioDevice 的客户端名
AUDIO_RATE = 16000                           # 16k 满足 FunASR；Pepper 可选 16000/22050/44100/48000
AUDIO_CHANNELS = 1                           # 上行单声道（ASR 只需前麦）
# ⚠️ NAOqi 2.5.10.7 上 4 麦通道顺序需真机确认；前麦通常为通道 0。
#    若实测静音/回声异常，改此值为 1/2/3（后/左/右）或查阅 ALMemory 通道顺序。
FRONT_MIC_CHANNEL = 0
AUDIO_DEINTERLEAVE = 0                        # 0=交织；1=分块（buffer 布局随之变化）

# ---- 本机文本朗读 ----
TTS_LANGUAGE = "Chinese"
TTS_SPEED = 90                                  # NAOqi 相对速度参数（百分比）

# ---- 运动安全（对齐 pepper_v1.yaml safety）----
MAX_MOVE_SPEED = 0.4          # m/s，三轮底盘物理上限（yaml: speed_limit_mps）
APPROACH_DISTANCE_M = 0.3     # approach 默认前移半步（老人场景礼仪，真机调参）
MOVE_BLOCKING = True          # moveTo 阻塞直到到位（简单可靠；长路径可改 False）

# ---- 失联看门狗（ADR-011 §决策3：断连 > N 秒 → 停运动）----
WATCHDOG_TIMEOUT_S = 15.0     # 主网关心跳超时阈值
HEARTBEAT_INTERVAL_S = 5.0    # 主网关建议心跳周期（< 超时阈值）

# ---- 反馈 ----
VERSION = "0.2.0"             # naoqi_bridge 实现版本（骨架为 0.1.0）
