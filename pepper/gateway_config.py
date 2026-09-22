# -*- coding: utf-8 -*-
"""Pepper 主网关（suiyue-pepper）配置常量，Python 3.13 运行。

与 naoqi_bridge/config.py 分离：本文件是主网关侧（Py3）配置；
naoqi_bridge/config.py 是桥侧（Py2.7）配置，两者经本地 IPC 协作。
"""
from __future__ import annotations
import os

# ---- 云端 xiaozhi-esp32-server WS（与 Otto/Reachy 同协议）----
# ⚠️ 端点路径 /xiaozhi/v1 依所部署 server 版本；若 server 用 /xiaozhi 请改。
DEFAULT_CLOUD_WS = os.environ.get("SUIYUE_CLOUD_WS", "ws://192.168.31.10:8000/xiaozhi/v1")
XIAOZHI_PROTOCOL_VERSION = "1.0.0"

# ---- 本地 naoqi_bridge IPC（127.0.0.1:9560 JSON 行）----
DEFAULT_IPC_HOST = "127.0.0.1"
DEFAULT_IPC_PORT = 9560

# ---- Pepper broker（仅 --auto-bridge 拉起子进程时用到）----
DEFAULT_QI_URL = os.environ.get("PEPPER_QI_URL", "tcp://pepper.local:9559")

# ---- 设备 ----
DEVICE_ID = os.environ.get("PEPPER_DEVICE_ID", "pepper-01")

# ---- 音频 ----
AUDIO_RATE = 16000
AUDIO_CHANNELS = 1
AUDIO_FRAME_DURATION_MS = 60
# 上行/下行音频编码：
#   raw   = PCM 零依赖（需 xiaozhi-server 支持 raw PCM 接收/下发）
#   opus  = 标准（需 opuslib + 系统 libopus；xiaozhi-server 多数要求 opus）
# ⚠️ 默认 opus（最贴近现有 Otto/Reachy 链路）；若 server 不支持 opus 且支持 raw，
#    设 PEPPER_AUDIO_FORMAT=raw 即可零依赖运行。
AUDIO_FORMAT = os.environ.get("PEPPER_AUDIO_FORMAT", "opus")
OPUS_APPLICATION = "voip"
OPUS_FRAME_SAMPLES = AUDIO_RATE * AUDIO_FRAME_DURATION_MS // 1000  # 960 @16k/60ms

# ---- 心跳（喂 naoqi_bridge 看门狗，桥侧 WATCHDOG_TIMEOUT=15s）----
HEARTBEAT_INTERVAL_S = 5.0

# ---- VAD（麦克风能量检测，控制 xiaozhi listen start/stop）----
VAD_SILENCE_MS = 800                       # 连续静音超过此值 -> listen stop
VAD_ENERGY_THRESHOLD = 300                 # int16 RMS 阈值（0-32767），低于=静音

# ---- emotion -> Pepper 动作原语（对齐 pepper_v1.yaml emotion_mapping）----
# 云端 LLM 输出 emotion 后，主网关据此映射成 naoqi_bridge 能执行的动作原语。
EMOTION_TO_ACTION = {
    "happy":     ("emote", {"animation": "Wave"}),
    "excited":   ("emote", {"animation": "Wave"}),
    "soothing":  ("posture", {"name": "Crouch"}),   # 蹲下降低视线高度安抚
    "curious":   ("head_nod", {}),
    "concerned": ("approach", {"distance": 0.3}),    # 走到老人身边停住
    "neutral":   ("posture", {"name": "Stand"}),
}

# ---- 自动拉起 Py2.7 桥（可选；--auto-bridge 时用到）----
DEFAULT_PY2_EXE = os.environ.get("PYTHON2_EXE", "python2.7")
