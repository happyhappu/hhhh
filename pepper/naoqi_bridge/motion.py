# -*- coding: utf-8 -*-
"""
运动/表情/急停控制器（对齐 pepper_v1.yaml action_primitives + emotion_mapping）。

- emote / approach / stop_all / posture / get_status / head_nod / head_shake
- 依赖：ALMotion / ALRobotPosture / ALAnimationPlayer / ALBasicAwareness（可选）

⚠️ 动画标签（如 "Wave"）与关节插值角度需 NAOqi 2.5.10.7 真机核对；
   未知标签会回退到关节级动作（点头/摇头走 ALMotion 角度插值，较稳）。
"""
from __future__ import print_function, absolute_import

import threading
import config as cfg


# 友好动作名 -> ALAnimationPlayer 行为路径（⚠️ 真机确认标签存在）
_ANIM_MAP = {
    "wave": "animations/Stand/Gestures/Hey_1",
    "hug": "animations/Stand/Gestures/Hug_1",
    "dance": "animations/Stand/Gestures/Dance_1",
    "happy": "animations/Stand/Emotions/Positive/Happy_1",
    "sad": "animations/Stand/Emotions/Negative/Sad_1",
    "excited": "animations/Stand/Emotions/Positive/Excited_1",
}

# The user's approved Stand animations. No path outside this list can be
# executed through the audio-only gesture channel.
SAFE_GESTURES = {
    "wave": "animations/Stand/Gestures/Hey_1",
    "nod_yes": "animations/Stand/Gestures/Yes_1",
    "shake_no": "animations/Stand/Gestures/No_1",
    "bow": "animations/Stand/Gestures/BowShort_1",
    "thinking": "animations/Stand/Gestures/Thinking_1",
    "show_sky": "animations/Stand/Gestures/ShowSky_1",
    "show_floor": "animations/Stand/Gestures/ShowFloor_1",
    "show_tablet": "animations/Stand/Gestures/ShowTablet_3",
    "please": "animations/Stand/Gestures/Please_1",
    "me": "animations/Stand/Gestures/Me_7",
    "calm_down": "animations/Stand/Gestures/CalmDown_1",
    "happy": "animations/Stand/Emotions/Positive/Happy_4",
    "shy": "animations/Stand/Emotions/Neutral/Embarrassed_1",
    # This robot stores BodyTalk_1 under Speaking/, not directly in BodyTalk/.
    "body_talk": "animations/Stand/BodyTalk/Speaking/BodyTalk_1",
    "dont_know": "animations/Stand/Gestures/IDontKnow_1",
    "bored": "animations/Stand/Emotions/Negative/Bored_1",
}


class MotionController(object):

    def __init__(self, proxies):
        self.p = proxies
        self._safe_gesture_lock = threading.Lock()
        self._gesture_future_lock = threading.Lock()
        self._gesture_future = None

    def safe_gesture(self, name):
        """Play an explicitly approved animation; never fall back to motion."""
        behavior = SAFE_GESTURES.get((name or "").lower())
        if not behavior:
            raise ValueError("gesture not in approved list")
        if not self._safe_gesture_lock.acquire(False):
            return {"played": False, "reason": "gesture_busy"}
        try:
            # The official NAOqi async form supports cancelling the specific
            # animation on shutdown/watchdog without relaxing robot motors.
            with self._gesture_future_lock:
                future = self.p.require("ALAnimationPlayer").run(behavior, _async=True)
                self._gesture_future = future
            future.value()
            return {"played": True, "animation": behavior}
        finally:
            with self._gesture_future_lock:
                self._gesture_future = None
            self._safe_gesture_lock.release()

    def stop_safe_gesture(self):
        with self._gesture_future_lock:
            future = self._gesture_future
            if future is not None:
                future.cancel()

    # ---- 表情/动画 ----
    def emote(self, animation="wave", params=None):
        anim = self.p.require("ALAnimationPlayer")
        key = (animation or "wave").lower()
        behavior = _ANIM_MAP.get(key, animation)
        try:
            anim.run(behavior)
            return {"played": behavior}
        except Exception as exc:
            # 回退：常见轻量动作改用关节级点头
            print("[motion] emote 回退到关节动作: %s" % exc)
            self.head_nod()
            return {"played": behavior, "fallback": "head_nod", "warn": str(exc)}

    def head_nod(self, params=None):
        """点头附和（ALMotion 关节插值，较稳）。"""
        motion = self.p.require("ALMotion")
        self._ensure_stiffness(motion, ["HeadYaw", "HeadPitch"])
        names = ["HeadPitch"]
        angles = [-0.25]   # 低头
        times = [0.4]
        motion.angleInterpolation(names, angles, times, True)
        motion.angleInterpolation(names, [0.0], [0.4], True)
        return {"gesture": "head_nod"}

    def head_shake(self, params=None):
        """摇头/疑惑（ALMotion 关节插值）。"""
        motion = self.p.require("ALMotion")
        self._ensure_stiffness(motion, ["HeadYaw", "HeadPitch"])
        names = ["HeadYaw"]
        angles = [0.4]    # 向右摆
        times = [0.4]
        motion.angleInterpolation(names, angles, times, True)
        motion.angleInterpolation(names, [0.0], [0.4], True)
        return {"gesture": "head_shake"}

    # ---- 靠近 ----
    def approach(self, distance=None, params=None):
        """靠近对话对象：面向说话人 + 前移半步（限速内）。

        params: {distance(float, m), face(bool 是否用 ALBasicAwareness 面向)}
        """
        motion = self.p.require("ALMotion")
        self._ensure_stiffness(motion, ["WheelFL", "WheelFR", "WheelB"])
        dist = float(distance if distance is not None else
                     (params or {}).get("distance", cfg.APPROACH_DISTANCE_M))
        dist = max(0.0, min(dist, 1.0))  # 安全夹紧

        # 可选：面向在场的人（ALBasicAwareness / ALTracker）
        awareness = self.p.get("ALBasicAwareness")
        if awareness is not None:
            try:
                awareness.setTrackingMode("FollowFace")  # ⚠️ 真机确认方法名
            except Exception as exc:
                print("[motion] ALBasicAwareness 面向失败(忽略): %s" % exc)
        motion.moveTo(dist, 0.0, 0.0, cfg.MOVE_BLOCKING)
        return {"approached": True, "distance_m": round(dist, 3)}

    # ---- 姿态 ----
    def posture(self, name="Stand", params=None):
        """切到预定义姿态：Stand / Sit / Crouch。"""
        rp = self.p.require("ALRobotPosture")
        rp.goToPosture(name, 0.5)
        return {"posture": name}

    # ---- 急停 ----
    def stop_all(self, params=None):
        """急停：杀掉所有运动任务 + 去刚度（电机松弛，靠跌倒保护兜底）。

        音频/视觉订阅的退订由 bridge.py 统一编排（持有各自引用）。
        """
        motion = self.p.get("ALMotion")
        if motion is not None:
            try:
                motion.killAllTasks()
            except Exception as exc:
                print("[motion] killAllTasks 异常(忽略): %s" % exc)
            try:
                motion.rest()  # 去刚度，电机松弛
            except Exception as exc:
                print("[motion] rest 异常(忽略): %s" % exc)
        return {"stopped": True}

    # ---- 状态上报 ----
    def get_status(self, params=None):
        """上报端侧状态，供云端健康看板。"""
        out = {"connected": True}
        rp = self.p.get("ALRobotPosture")
        if rp is not None:
            try:
                out["posture"] = rp.getPostureFamily()
            except Exception:
                out["posture"] = "unknown"
        mem = self.p.get("ALMemory")
        if mem is not None:
            try:
                # 电量百分比（0-1）；⚠️ 真机确认 key 存在
                out["battery"] = mem.getData(
                    "Device/SubDeviceList/Battery/Charge/Sensor/Value")
            except Exception:
                out["battery"] = None
            try:
                out["robot_name"] = mem.getData("RobotConfig/Head/PhoneCarrier")
            except Exception:
                out["robot_name"] = None
        return out

    # ---- 内部工具 ----
    @staticmethod
    def _ensure_stiffness(motion, joints):
        try:
            motion.setStiffnesses(joints, 1.0)
        except Exception as exc:
            print("[motion] setStiffnesses 异常(忽略): %s" % exc)
