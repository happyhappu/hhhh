# -*- coding: utf-8 -*-
"""
Pepper NAOqi proxy 集中管理。

- REQUIRED：本系统动作/音频/平板/状态上报必需，缺失即报错（真机若缺按 yaml 降级）。
- OPTIONAL：感知/导航增强，缺失则优雅降级（不阻塞主流程）。
- 对齐 pepper_v1.yaml 的 proxies_used / disabled_cloud_services。

⚠️ 仅按 NAOqi 2.5 培训文档实证命名编写，未经 NAOqi 2.5.10.7 真机验证；
   若某 proxy 在真机上 `service not found`，自动记为 None 并降级，不影响其余功能。
"""
from __future__ import print_function, absolute_import

# 命名以 NAOqi 2.5 大学培训文档实证为准
REQUIRED = [
    "ALMotion",          # 关节/轮子运动、killAllTasks 急停、moveTo 基础移动
    "ALRobotPosture",    # Stand/Sit/Crouch 预定义姿态
    "ALAnimationPlayer", # 播放预制动画（挥手/拥抱等）
    "ALTabletService",   # 平板渲染 companion Web UI
    "ALMemory",          # 传感器/事件/信号枢纽（订阅 HeadTouched / FaceDetected 等）
    "ALAudioDevice",     # 麦克风采集（音频上云入口）
]
OPTIONAL = [
    "ALBasicAwareness",  # 注视/在场（approach 时面向说话人）
    "ALNavigation",      # 拓扑地图导航【可选·降级】
    "ALTracker",         # 跟踪人体（approach 增强）
    "ALFaceDetection",   # 人脸检测/识别（在场感知）
    "ALPeoplePerception",  # 人体感知（计数/距离）
    "ALSoundLocalization",  # 声源定位（辅助面向说话人）
]


class PepperProxies(object):
    """惰性获取并缓存所有 NAOqi proxy，记录可用性。"""

    def __init__(self, session):
        self.session = session
        self.available = {}
        self._probe()

    def _probe(self):
        for name in REQUIRED + OPTIONAL:
            try:
                self.available[name] = self.session.service(name)
            except Exception as exc:  # 真机可能 service not found
                self.available[name] = None
                print("[proxies] WARN: %s 不可用 -> 降级: %s" % (name, exc))

    def get(self, name):
        """返回 proxy 或 None（不可用）。"""
        return self.available.get(name)

    def require(self, name):
        """返回 proxy；若必需 proxy 缺失则抛 RuntimeError。"""
        proxy = self.available.get(name)
        if proxy is None:
            raise RuntimeError("%s 不可用（真机未提供或禁用）" % name)
        return proxy

    def has(self, name):
        return self.available.get(name) is not None

    def summary(self):
        out = {}
        for name in REQUIRED + OPTIONAL:
            out[name] = self.available.get(name) is not None
        return out
