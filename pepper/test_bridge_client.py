# -*- coding: utf-8 -*-
"""
Pepper 主网关 ↔ qi-bridge 的 Py3 联调客户端（开发/自测用，不依赖 Py2 SDK）。

用途：在没有 Pepper 真机、甚至没有 pynaoqi 的环境里，验证：
  1. 本地 TCP IPC 协议（JSON 行）收发是否正常；
  2. 音频帧 / 感知事件的上行格式是否符合约定；
  3. 桥的派发与响应是否按预期。

运行：
  python3 test_bridge_client.py            # 默认 127.0.0.1:9560
  python3 test_bridge_client.py --port 9560 --host 127.0.0.1

注意：本文件是 Py3，与 naoqi_bridge（Py2.7）分开放置，避免解释器混用。
桥未启动时连接会被拒绝，属预期（先启动 bridge.py）。
"""
from __future__ import print_function, absolute_import

import sys
import os
import json
import time
import socket
import argparse
import threading

try:
    import Queue as queue
except ImportError:
    import queue


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9560


def _recv_lines(sock, out_queue):
    """后台线程：按 \\n 切分 JSON 行，放入 out_queue。"""
    buf = b""
    while True:
        try:
            data = sock.recv(4096)
        except Exception:
            out_queue.put(None)  # 连接断开
            return
        if not data:
            out_queue.put(None)
            return
        buf += data
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                try:
                    out_queue.put(json.loads(line.decode("utf-8")))
                except ValueError:
                    out_queue.put({"_raw": line.decode("utf-8", "replace")})


def main():
    ap = argparse.ArgumentParser(description="Pepper bridge IPC 联调客户端 (Py3)")
    ap.add_argument("--host", default=DEFAULT_HOST)
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--audio-frames", type=int, default=3,
                    help="audio_start 后收集多少音频帧再停（仅验证格式）")
    args = ap.parse_args()

    sock = socket.create_connection((args.host, args.port))
    sock.settimeout(5.0)
    print("[client] 已连接 %s:%d" % (args.host, args.port))

    inbox = queue.Queue()
    t = threading.Thread(target=_recv_lines, args=(sock, inbox))
    t.daemon = True
    t.start()

    def send(action, params=None, mid=None):
        msg = {"action": action}
        if mid is not None:
            msg["id"] = mid
        if params is not None:
            msg["params"] = params
        sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        print("[client] -> %s" % json.dumps(msg, ensure_ascii=False))

    def wait_response(want_id=None, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            try:
                obj = inbox.get(timeout=0.5)
            except Exception:
                continue
            if obj is None:
                print("[client] ! 连接已断开")
                return None
            if want_id is None or obj.get("id") == want_id:
                return obj
            # 可能是异步音频帧/事件，打印但不消费匹配
            print("[client] <- async: %s" % json.dumps(obj, ensure_ascii=False)[:120])
        print("[client] ! 等待响应超时")
        return None

    try:
        # 1) 心跳
        send("ping", mid=1)
        wait_response(1)

        # 2) 状态
        send("get_status", mid=2)
        wait_response(2)

        # 3) 动作（真机才会真正移动；无真机时桥会回 proxy 不可用错误，属预期）
        send("emote", {"animation": "wave"}, mid=3)
        wait_response(3)
        send("approach", {"distance": 0.3}, mid=4)
        wait_response(4)

        # 4) 音频链路（验证上行格式；无真机时桥回 audio_start 但无帧）
        send("audio_start", mid=5)
        r5 = wait_response(5)
        collected = 0
        end = time.time() + 8.0
        while collected < args.audio_frames and time.time() < end:
            try:
                obj = inbox.get(timeout=0.5)
            except Exception:
                continue
            if obj is None:
                break
            if obj.get("type") == "audio":
                collected += 1
                size = len(obj.get("data_b64", ""))
                print("[client] <- audio frame #%d (rate=%s ch=%s b64=%dB)"
                      % (collected, obj.get("rate"), obj.get("channels"), size))
            else:
                print("[client] <- %s" % json.dumps(obj, ensure_ascii=False)[:120])
        send("audio_stop", mid=6)
        wait_response(6)

        # 5) 急停
        send("stop_all", mid=7)
        wait_response(7)

        print("[client] 联调完成（无错误即 IPC 协议正常）")
    except KeyboardInterrupt:
        pass
    finally:
        try:
            sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
