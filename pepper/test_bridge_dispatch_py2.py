# -*- coding: utf-8 -*-
"""Exercise Python 2 bridge IPC permissions without connecting to Pepper."""
from __future__ import print_function
import json
import os
import Queue
import sys
import threading
import time
import unittest

BRIDGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'naoqi_bridge')
if BRIDGE not in sys.path:
    sys.path.insert(0, BRIDGE)
import bridge


class FakePepper(object):
    def __init__(self, allow_gestures=True):
        self.audio_only = True
        self.allow_gestures = allow_gestures
        self.calls = []
        self.called = threading.Event()

    def safe_gesture(self, params):
        self.calls.append(('safe_gesture', params))
        self.called.set()
        return {'played': True}

    def audio_stop(self, params):
        self.calls.append(('audio_stop', params))
        return {'audio': 'stopped'}

    def audio_start(self, on_frame, params):
        self.calls.append(('audio_start', params))
        self.on_frame = on_frame
        return {'audio': 'started'}


class FakeHandler(bridge._Handler):
    def __init__(self, pepper):
        self.server = type('Server', (object,), {'pepper': pepper})()
        self.sent = []
        self.audio_queue = Queue.Queue()
        self._audio_thread = None

    def _send(self, result):
        self.sent.append(result)


class DispatchTests(unittest.TestCase):
    def test_only_audio_and_explicit_safe_gestures_are_allowed(self):
        pepper = FakePepper(True)
        h = FakeHandler(pepper)
        for action in ('approach', 'navigate', 'posture', 'emote', 'tablet_render'):
            bridge._Handler._dispatch(h, json.dumps({'id': action, 'action': action}).encode('utf-8'))
        self.assertEqual(len(h.sent), 5)
        self.assertTrue(all('error' in x for x in h.sent))
        bridge._Handler._dispatch(h, json.dumps({'id': 1, 'action': 'safe_gesture',
                                               'params': {'animation': 'wave'}}).encode('utf-8'))
        self.assertTrue(pepper.called.wait(1))
        self.assertEqual(pepper.calls, [('safe_gesture', {'animation': 'wave'})])

    def test_safe_gestures_require_explicit_enable(self):
        pepper = FakePepper(False)
        h = FakeHandler(pepper)
        bridge._Handler._dispatch(h, json.dumps({'id': 1, 'action': 'safe_gesture'}).encode('utf-8'))
        self.assertEqual(len(h.sent), 1)
        self.assertIn('error', h.sent[0])
        self.assertEqual(pepper.calls, [])

    def test_microphone_can_stop_and_restart_on_same_connection(self):
        pepper = FakePepper()
        h = FakeHandler(pepper)
        for action in ('audio_start', 'audio_stop', 'audio_start'):
            bridge._Handler._dispatch(h, json.dumps({'id': action, 'action': action}).encode('utf-8'))
            if action == 'audio_start':
                pepper.on_frame(b'\x00\x00', 16000, 1)
        deadline = time.time() + 1
        while len([x for x in h.sent if x.get('type') == 'audio']) < 2 and time.time() < deadline:
            time.sleep(.01)
        self.assertEqual(len([x for x in h.sent if x.get('type') == 'audio']), 2)
        self.assertTrue(h._audio_thread.is_alive())
        h.audio_queue.put(None)


if __name__ == '__main__':
    unittest.main()
