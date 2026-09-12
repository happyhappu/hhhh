# -*- coding: utf-8 -*-
"""
Pepper 端侧 qi-bridge 主入口（Python 2.7 运行）

依赖：pynaoqi-python2.7-2.5.7.1-win32-vs2013（import qi / import naoqi，Py2.7-only）
运行前（Windows）：
    set PYTHONPATH=<sdk>\lib
    set PATH=<sdk>\bin;<sdk>\lib;%PATH%
    python2.7 bridge.py --qi-url tcp://<pepper-ip>:9559

职责：连 Pepper broker(:9559)，把云端（Py3 主网关）下发的
{action, params} 派发到 self.pepper.*，并把麦克风音频帧回传主网关。
主网关 ↔ 本桥 经本地 TCP（127.0.0.1:9560）以 JSON 行协议通信
（详见 README.md）。本桥只作协议/动作桥，不含任何 LLM/ASR/TTS。

⚠️ 本文件按 NAOqi 2.5 培训文档接口形状编写，未经真机验证；
   真机 2.9 上若某 proxy `service not found`，按 pepper_v1.yaml 降级处理。
"""
import sys
import os
import json
import base64
import threading
import SocketServer  # Py2.7；Py3 为 socketserver

if sys.version_info[0] != 2:
    raise RuntimeError("naoqi_bridge 必须用 Python 2.7 运行（pynaoqi 2.5.7.1 仅 Py2.7）")

import qi

from audio import start_audio_stream, stop_audio_stream

DEFAULT_QI_URL = "tcp://pepper.local:9559"
DEFAULT_IPC_HOST = "127.0.0.1"
DEFAULT_IPC_PORT = 9560
AUDIO_CLIENT = "pepper_bridge"


class Pepper(object):
    """把云端动作原语映射到 NAOqi proxy。self.pepper 即 MCP 侧看到的实体。"""

    def __init__(self, session):
        self.session = session
        self.motion = session.service("ALMotion")
        self.posture = session.service("ALRobotPosture")
        self.anim = session.service("ALAnimationPlayer")
        self.awareness = session.service("ALBasicAwareness")
        self.tablet = session.service("ALTabletService")
        self.memory = session.service("ALMemory")
        # ALTextToSpeech / ALDialog / ALSpeechRecognition 已禁用（改云端），此处不实例化
        self._stop = threading.Event()

    # ---- 动作原语（对齐 pepper_v1.yaml action_primitives）----

    def emote(self, animation="Wave", params=None):
        """播放预制动画（挥手/拥抱等）。animation 为 ALAnimationPlayer 标签或 .xar 路径。"""
        if animation and animation.endswith(".xar"):
            self.anim.playWeb("^runBehaviorUser/" + animation)
        else:
            # 常见轻量动作走 ALAnimationPlayer 内置行为
            self.anim.run("animations/Stand/Emotions/Positive/" + animation)
        return {"played": animation}

    def approach(self, target="user", params=None):
        """靠近对话对象：基础用 ALMotion.moveTo + 面向；人形跟踪可接 ALTracker。"""
        # 简化：转向说话人方向并小步前移（0.4 m/s 限速在 NAOqi 内约束）
        self.motion.moveTo(0.3, 0.0, 0.0)  # 前移 0.3m，真机按需调参
        return {"approached": target}

    def navigate(self, goal, params=None):
        """拓扑/目标点导航。纯 qi 路径用 ALMotion.moveTo；ALNavigation 列为可选降级。"""
        if isinstance(goal, (list, tuple)) and len(goal) >= 2:
            x, y = goal[0], goal[1]
            theta = goal[2] if len(goal) > 2 else 0.0
            self.motion.moveTo(x, y, theta)
            return {"navigated_to": [x, y, theta]}
        return {"error": "goal 需为 [x, y, theta]"}

    def patrol(self, route, params=None):
        """巡游多个航点。"""
        for wp in (route or []):
            self.navigate(wp)
        return {"patrolled": len(route or [])}

    def tablet_render(self, html, params=None):
        """平板渲染 companion Web UI（问候语/字幕/表情）。"""
        self.tablet.showWebview(html)
        return {"tablet": "rendered"}

    def stop_all(self):
        """急停：killAllTasks + 停止音频。失联看门狗触发。"""
        try:
            self.motion.killAllTasks()
        except Exception:
            pass
        stop_audio_stream()
        self._stop.set()
        return {"stopped": True}

    def get_status(self):
        """上报端侧状态（电量/姿态/连接），供云端健康看板。"""
        try:
            posture = self.posture.getPostureFamily()
        except Exception:
            posture = "unknown"
        return {"posture": posture, "audio_streaming": not self._stop.is_set()}


class BridgeServer(SocketServer.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr, pepper, audio_on=False):
        SocketServer.ThreadingTCPServer.__init__(self, addr, _Handler)
        self.pepper = pepper
        self.audio_on = audio_on


class _Handler(SocketServer.StreamRequestHandler):
    def handle(self):
        pepper = self.server.pepper
        sock_file = self.rfile
        while True:
            line = sock_file.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
            except ValueError:
                self._send({"error": "bad json"})
                continue
            action = msg.get("action")
            mid = msg.get("id")
            params = msg.get("params") or {}
            try:
                if action == "audio_start":
                    self.server.audio_on = True
                    start_audio_stream(pepper.session, self._on_audio_frame)
                    self._send({"id": mid, "ok": True, "result": {"audio": "started"}})
                elif action == "audio_stop":
                    stop_audio_stream()
                    self._send({"id": mid, "ok": True, "result": {"audio": "stopped"}})
                elif hasattr(pepper, action):
                    fn = getattr(pepper, action)
                    result = fn(**params) if params else fn()
                    self._send({"id": mid, "ok": True, "result": result})
                else:
                    self._send({"id": mid, "error": "unknown action: %s" % action})
            except Exception as e:  # 真机异常原样回传，便于排查
                self._send({"id": mid, "error": "%s: %s" % (type(e).__name__, e)})

    def _on_audio_frame(self, pcm_bytes, rate, channels):
        # 麦克风帧 → 主网关（→ 云 FunASR）。base64 仅骨架用，性能优化见 README。
        self._send({
            "type": "audio",
            "rate": rate,
            "channels": channels,
            "data_b64": base64.b64encode(pcm_bytes).decode("ascii"),
        })

    def _send(self, obj):
        try:
            self.wfile.write((json.dumps(obj) + "\n").encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Pepper qi-bridge (Py2.7)")
    ap.add_argument("--qi-url", default=os.environ.get("PEPPER_QI_URL", DEFAULT_QI_URL))
    ap.add_argument("--ipc-host", default=DEFAULT_IPC_HOST)
    ap.add_argument("--ipc-port", type=int, default=DEFAULT_IPC_PORT)
    args = ap.parse_args()

    session = qi.Session()
    session.connect(args.qi_url)
    print("[bridge] connected to Pepper broker: %s" % args.qi_url)

    pepper = Pepper(session)
    server = BridgeServer((args.ipc_host, args.ipc_port), pepper)
    print("[bridge] IPC listening on %s:%d (Py3 main gateway connects here)" %
          (args.ipc_host, args.ipc_port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pepper.stop_all()
        server.shutdown()


if __name__ == "__main__":
    main()
