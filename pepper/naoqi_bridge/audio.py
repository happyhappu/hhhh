# -*- coding: utf-8 -*-
"""
Pepper 麦克风音频捕获（Python 2.7）

参照《NAOqi Python SDK 大学培训文档》2-3 节 audio_record.py：
经局域网把 Pepper 麦克风录成 WAV/原始 PCM 传到本地 PC。
本模块订阅前置麦克风，把 PCM 帧经回调 on_frame(pcm_bytes, rate, channels)
推给 bridge.py → 主网关（→ 云 FunASR 流式识别）。

接口形状（NAOqi 2.5/2.9 通用）：
  ALAudioDevice.setClientPreferences(name, rate, channels, deinterleave)
  ALAudioDevice.subscribe(name)
  ALMemory.subscribeToEvent("ALAudioDevice/<name>", cb)  -> cb(dataName, value, msg)
  value 为 int16 PCM 二进制缓冲（单/双声道，rate 由 setClientPreferences 决定）

⚠️ 仅按文档接口形状编写，未经真机验证。真机 2.9 上若回调签名/事件名
   有出入，以此文件为唯一改动点，不影响 bridge.py 其余逻辑。
"""
import qi

_CLIENT = "pepper_bridge"
_RATE = 16000
_CHANNELS = 1

_audio_state = {"running": False, "callback": None}


def _on_audio_event(dataName, value, message):
    """ALMemory 事件回调：value 即一帧 int16 PCM。"""
    cb = _audio_state.get("callback")
    if cb and value is not None:
        cb(value if isinstance(value, str) else str(value), _RATE, _CHANNELS)


def start_audio_stream(session, on_frame, sample_rate=_RATE, channels=_CHANNELS,
                       client_name=_CLIENT):
    """订阅 Pepper 前置麦克风，逐帧回调 PCM。

    on_frame(pcm_bytes, rate, channels) 由调用方（bridge.py）提供。
    """
    _audio_state["callback"] = on_frame
    _audio_state["running"] = True

    audio_device = session.service("ALAudioDevice")
    # 单声道、16k、不分离多麦（deinterleave=0）-> 简化上行
    audio_device.setClientPreferences(client_name, sample_rate, channels, 0)
    audio_device.subscribe(client_name)

    memory = session.service("ALMemory")
    memory.subscribeToEvent("ALAudioDevice/" + client_name, _on_audio_event)
    return True


def stop_audio_stream():
    """停止麦克风订阅。"""
    if not _audio_state["running"]:
        return
    _audio_state["running"] = False
    _audio_state["callback"] = None
    # session 在调用方持有；此处仅置标志位，资源释放由 broker 侧超时回收。
    # 若需显式退订，可在 bridge.py 持有 audio_device 引用后调用 unsubscribe。
