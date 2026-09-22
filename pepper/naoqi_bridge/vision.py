# -*- coding: utf-8 -*-
"""
在场感知控制器（可选）：订阅人脸/人体事件，经回调上抛给主网关。

- 对齐 pepper_v1.yaml proxies_used: ALFaceDetection / ALPeoplePerception
- 事件经 ALMemory.subscribeToEvent 订阅；回调 on_event(name, data) 由 bridge 提供，
  用于（例如）云端知道"有人靠近"以主动打招呼。

⚠️ 事件名（FaceDetected / PeoplePerception/PeopleDetected）以 NAOqi 2.5 文档为准，
   真机 2.5.10.7 若有差异，仅改本文件 EVENT_* 常量即可。
"""
from __future__ import print_function, absolute_import

# ⚠️ 真机确认事件名
EVENT_FACE = "FaceDetected"
EVENT_PEOPLE = "PeoplePerception/PeopleDetected"


class PerceptionController(object):

    def __init__(self, proxies):
        self.p = proxies
        self._mem = None
        self._cb = None
        self._subscribed = []

    def start(self, on_event, params=None):
        """订阅人脸/人体事件。

        on_event(event_name, payload_dict) 由调用方（bridge）提供。
        """
        mem = self.p.get("ALMemory")
        if mem is None:
            return {"error": "ALMemory 不可用，无法订阅感知事件"}
        self._mem = mem
        self._cb = on_event
        subscribed = []
        if self.p.has("ALFaceDetection"):
            try:
                mem.subscribeToEvent(EVENT_FACE, self._on_face)
                subscribed.append(EVENT_FACE)
            except Exception as exc:
                print("[vision] 订阅 %s 失败(忽略): %s" % (EVENT_FACE, exc))
        if self.p.has("ALPeoplePerception"):
            try:
                mem.subscribeToEvent(EVENT_PEOPLE, self._on_people)
                subscribed.append(EVENT_PEOPLE)
            except Exception as exc:
                print("[vision] 订阅 %s 失败(忽略): %s" % (EVENT_PEOPLE, exc))
        self._subscribed = subscribed
        return {"perception": "started", "events": subscribed}

    def stop(self, params=None):
        """退订所有感知事件。"""
        if self._mem is None:
            return {"perception": "stopped", "events": []}
        for ev in self._subscribed:
            try:
                self._mem.unsubscribeToEvent(ev)
            except Exception as exc:
                print("[vision] 退订 %s 失败(忽略): %s" % (ev, exc))
        self._subscribed = []
        return {"perception": "stopped", "events": []}

    # ---- ALMemory 事件回调（NAOqi 调用签名: cb(value) 或 cb(dataName, value)）----
    def _on_face(self, *args):
        value = args[-1] if args else None
        if self._cb is not None:
            self._cb(EVENT_FACE, self._safe_payload(value))

    def _on_people(self, *args):
        value = args[-1] if args else None
        if self._cb is not None:
            self._cb(EVENT_PEOPLE, self._safe_payload(value))

    @staticmethod
    def _safe_payload(value):
        # value 可能是列表/字典/二进制；尽量原样上抛，主网关按需解析
        try:
            return value
        except Exception:
            return None
