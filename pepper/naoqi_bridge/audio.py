# -*- coding: utf-8 -*-
"""Pepper audio through NAOqi 2.5 qi.Session (Python 2.7)."""
from __future__ import print_function
import threading
import qi
import config as cfg

_AUDIO_STATE = {"session": None, "module": None, "id": None, "running": False}


class MicrophoneCapture(object):
    def __init__(self, on_frame):
        self.on_frame = on_frame
        self.frames = 0

    @qi.bind(returnType=qi.Void, paramsType=[qi.Int32, qi.Int32, qi.List(qi.Int32), qi.Buffer])
    def processRemote(self, channels, samples, stamp, buffer):
        # qi represents the binary ALValue as a Python bytearray.
        pcm = str(buffer)
        if channels != 1 or len(pcm) != samples * 2:
            print("[audio] Unexpected callback format: %s/%s/%s" % (channels, samples, len(pcm)))
            return
        self.frames += 1
        if self.frames == 1:
            print("[audio] First microphone frame: %s bytes, %sHz" % (len(pcm), cfg.AUDIO_RATE))
        self.on_frame(pcm, cfg.AUDIO_RATE, 1)


def start_audio_stream(qi_url, on_frame, sample_rate=cfg.AUDIO_RATE,
                       channels=cfg.AUDIO_CHANNELS, client_name=cfg.AUDIO_CLIENT_NAME):
    if _AUDIO_STATE["running"]:
        return True
    session = qi.Session()
    session.listen("tcp://0.0.0.0:9562")
    session.connect(qi_url)
    module = MicrophoneCapture(on_frame)
    service_id = session.registerService(client_name, module)
    try:
        audio = session.service("ALAudioDevice")
        audio.setClientPreferences(client_name, sample_rate, 3, 0)
        audio.subscribe(client_name)
    except Exception:
        session.unregisterService(service_id)
        session.close()
        raise
    _AUDIO_STATE.update(session=session, module=module, id=service_id, running=True)
    print("[audio] Microphone subscribed: %sHz, mono, callback TCP 9562" % sample_rate)
    return True


def stop_audio_stream():
    session = _AUDIO_STATE["session"]
    if session is None:
        return
    try:
        session.service("ALAudioDevice").unsubscribe(cfg.AUDIO_CLIENT_NAME)
    finally:
        session.unregisterService(_AUDIO_STATE["id"])
        session.close()
        _AUDIO_STATE.update(session=None, module=None, id=None, running=False)
    print("[audio] Microphone unsubscribed")


_PLAY_LOCK = __import__("threading").Lock()


def play_audio(pcm, rate, channels, session, sample_width=2):
    """Send interleaved stereo PCM over NAOqi; no cross-machine file path."""
    import audioop
    import time
    if not pcm:
        return {"played": False, "reason": "empty"}
    if sample_width != 2 or channels not in (1, 2) or len(pcm) % (2 * channels):
        raise ValueError("Expected aligned 16-bit mono/stereo PCM")
    with _PLAY_LOCK:
        audio = session.service("ALAudioDevice")
        output_rate = audio.getParameter("outputSampleRate")
        if rate != output_rate:
            pcm = audioop.ratecv(pcm, 2, channels, rate, output_rate, None)[0]
        if channels == 1:
            pcm = audioop.tostereo(pcm, 2, 1.0, 1.0)
        started, sent = time.time(), 0
        for offset in range(0, len(pcm), 4096 * 4):
            block = pcm[offset:offset + 4096 * 4]
            frames = len(block) // 4
            if not audio.sendRemoteBufferToOutput(frames, bytearray(block)):
                raise RuntimeError("Robot audio buffer rejected")
            sent += frames
            delay = started + float(sent) / output_rate - time.time()
            if delay > 0:
                time.sleep(delay)
        return {"played": True, "frames": sent, "output_rate": output_rate,
                "duration_s": round(float(sent) / output_rate, 3)}
