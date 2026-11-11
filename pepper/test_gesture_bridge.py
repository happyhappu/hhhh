"""Verify the NAOqi bridge gesture whitelist without moving a robot."""
import os
import sys
import threading
import unittest

bridge_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'naoqi_bridge')
if bridge_dir not in sys.path:
    sys.path.insert(0, bridge_dir)
import motion
import gateway_config


class FakeFuture:
    def __init__(self, wait=False):
        self.event = threading.Event()
        self.cancelled = False
        if not wait:
            self.event.set()

    def value(self):
        if not self.event.wait(2):
            raise RuntimeError('test future timed out')

    def cancel(self):
        self.cancelled = True
        self.event.set()


class FakeAnimationPlayer:
    def __init__(self, wait=False):
        self.calls = []
        self.future = FakeFuture(wait=wait)
        self.started = threading.Event()

    def run(self, path, **kwargs):
        self.calls.append((path, kwargs))
        self.started.set()
        return self.future


class FakeProxies:
    def __init__(self, player):
        self.player = player

    def require(self, name):
        if name != 'ALAnimationPlayer':
            raise AssertionError('unexpected robot service')
        return self.player


class GestureWhitelistTests(unittest.TestCase):
    def test_all_sixteen_requested_gestures_are_whitelisted(self):
        self.assertEqual(len(motion.SAFE_GESTURES), 16)
        self.assertEqual(motion.SAFE_GESTURES['wave'], 'animations/Stand/Gestures/Hey_1')
        self.assertEqual(motion.SAFE_GESTURES['body_talk'],
                         'animations/Stand/BodyTalk/Speaking/BodyTalk_1')
        self.assertTrue(all(path.startswith('animations/Stand/')
                            for path in motion.SAFE_GESTURES.values()))
        self.assertEqual(len(gateway_config.SERVER_EMOTION_TO_GESTURE), 21)
        self.assertEqual(len(gateway_config.SERVER_EMOTION_TO_EMOJI), 21)
        self.assertTrue(set(g for g in gateway_config.SERVER_EMOTION_TO_GESTURE.values() if g)
                        <= set(motion.SAFE_GESTURES))

    def test_safe_gesture_uses_only_approved_animation(self):
        player = FakeAnimationPlayer()
        controller = motion.MotionController(FakeProxies(player))
        result = controller.safe_gesture('wave')
        self.assertTrue(result['played'])
        self.assertEqual(player.calls, [('animations/Stand/Gestures/Hey_1', {'_async': True})])
        with self.assertRaises(ValueError):
            controller.safe_gesture('animations/Stand/Gestures/Anything')
        self.assertEqual(len(player.calls), 1)

    def test_stop_cancels_only_the_inflight_animation(self):
        player = FakeAnimationPlayer(wait=True)
        controller = motion.MotionController(FakeProxies(player))
        worker = threading.Thread(target=controller.safe_gesture, args=('wave',))
        worker.start()
        self.assertTrue(player.started.wait(1))
        controller.stop_safe_gesture()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertTrue(player.future.cancelled)


if __name__ == '__main__':
    unittest.main()
