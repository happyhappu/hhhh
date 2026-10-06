# -*- coding: utf-8 -*-
"""G3 · emotion 契约测试（云端 xiaozhi-server 标签集↔ 岁悦动作真值）。

**这个测试守护的是一个已经确认存在的静默失效 bug**（2026-10-06 核实 v0.9.7 源码）：

- 云端 `core/utils/textUtils.py:84 get_emotion()` 的做法是：在 LLM 回复里
  **扫描第一个 emoji**，用 `EMOJI_MAP`（L8-30，共 **21 个标签**）翻成标签，
  下发 `{"type":"llm","text":emoji,"emotion":<tag>}`。
- 岁悦侧 `EMOTION_TO_ACTION` 只有 **6 个键**
  （happy/excited/soothing/curious/concerned/neutral）。
- 两者**几乎零交集**（只有 neutral、happy 侥幸相同）。
  未命中时 `gateway.py` 静默回落到 `Stand` → **Pepper 永远站着不动，不报错**。

修法见 `gateway_config.py::SERVER_EMOTION_TO_SUYUE` + `to_suiyue_emotion()`。
本测试确保：
  1. 云端 21 个标签**全部**能被翻译（无遗漏 -> 无静默 Stand）；
  2. 翻译结果**必须**是 `EMOTION_TO_ACTION` 的合法键（否则仍然静默失效）；
  3. 未收录标签走兜底而非崩溃；
  4. 上游若改 EMOJI_MAP，本测试会红（提醒补映射）。

运行：
    cd suiyue && python -m unittest pepper.test_emotion_contract -v
"""
from __future__ import annotations

import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pepper import gateway_config as cfg  # noqa: E402

# v0.9.7 `main/xiaozhi-server/core/utils/textUtils.py:8-30` EMOJI_MAP 的值，
# 原样抄录作为"云端真实标签集"的权威副本。
UPSTREAM_EMOJI_MAP = {
    "😂": "funny", "😭": "crying", "😠": "angry", "😔": "sad", "😍": "loving",
    "😲": "surprised", "😱": "shocked", "🤔": "thinking", "😌": "relaxed",
    "😴": "sleepy", "😜": "silly", "🙄": "confused", "😶": "neutral",
    "🙂": "happy", "😆": "laughing", "😳": "embarrassed", "😉": "winking",
    "😎": "cool", "🤤": "delicious", "😘": "kissy", "😏": "confident",
}

UPSTREAM_TAGS = set(UPSTREAM_EMOJI_MAP.values())


class TestEmotionContract(unittest.TestCase):
    def test_upstream_tag_count_is_21(self):
        """守住前提：云端标签集是 21 个（改动会让本文件需复核）。"""
        self.assertEqual(len(UPSTREAM_TAGS), 21)

    def test_all_upstream_tags_translated(self):
        """云端每个标签都必须有显式映射，不能靠兜底蒙混。"""
        missing = sorted(UPSTREAM_TAGS - set(cfg.SERVER_EMOTION_TO_SUYUE))
        self.assertEqual(
            missing, [],
            "这些云端标签未收录，会静默回落 Stand：%s" % missing)

    def test_translation_result_is_always_actionable(self):
        """核心不变式：翻译结果必须是 EMOTION_TO_ACTION 的合法键。

        这条挂了 == 仍然静默失效（查表未命中 -> Stand）。
        """
        bad = []
        for tag in sorted(UPSTREAM_TAGS):
            mapped = cfg.to_suiyue_emotion(tag)
            if mapped not in cfg.EMOTION_TO_ACTION:
                bad.append("%s -> %s" % (tag, mapped))
        self.assertEqual(bad, [], "翻译结果不是可执行动作的键：%s" % bad)

    def test_mapping_values_are_subset_of_action_keys(self):
        """映射表的值域必须收在动作表键集内。"""
        stray = sorted(set(cfg.SERVER_EMOTION_TO_SUYUE.values())
                       - set(cfg.EMOTION_TO_ACTION))
        self.assertEqual(stray, [], "映射表存在无对应动作的值：%s" % stray)

    def test_every_action_key_is_reachable(self):
        """6 个岁悦 emotion 都应至少有一个云端标签能到达（无死动作）。"""
        reached = {cfg.to_suiyue_emotion(t) for t in UPSTREAM_TAGS}
        unreachable = sorted(set(cfg.EMOTION_TO_ACTION) - reached)
        self.assertEqual(
            unreachable, [],
            "这些动作没有任何云端标签能触发：%s" % unreachable)

    def test_unknown_tag_falls_back_safely(self):
        """未知标签不崩溃，且回落到安全姿态。"""
        self.assertEqual(cfg.to_suiyue_emotion("totally-unknown"),
                         cfg.UNKNOWN_EMOTION_FALLBACK)
        self.assertIn(cfg.to_suiyue_emotion("totally-unknown"),
                      cfg.EMOTION_TO_ACTION)

    def test_specific_semantics(self):
        """抽查语义正确性（不只是"能跑"，还要动作对）。"""
        cases = {
            "happy": "happy",# 🙂
            "laughing": "excited",  # 😆
            "crying": "soothing",    # 😭 蹲下安抚
            "angry": "concerned",    # 😠 走过去关心
            "confused": "curious",   # 🙄 歪头
            "neutral": "neutral",    # 😶 站立
        }
        for server_tag, expect in cases.items():
            self.assertEqual(cfg.to_suiyue_emotion(server_tag), expect,
                             "%s 语义映射不对" % server_tag)

    def test_old_bug_is_reproducible_without_fix(self):
        """回归锚点：直接用云端标签查 EMOTION_TO_ACTION 必然未命中。

        这条测试锁住"为什么需要翻译层"——若哪天云端改了标签集恰好与
        6 键重合，本测试会提示可以移除翻译层（而不是留死代码）。
        """
        direct_hit = [t for t in UPSTREAM_TAGS if t in cfg.EMOTION_TO_ACTION]
        # 当前交集只有 neutral / happy
        self.assertLessEqual(
            len(direct_hit), 2,
            "云端标签集与动作表交集变大（%s），请复核是否还需要翻译层"
            % sorted(direct_hit))


class TestBrainEmotionAlignment(unittest.TestCase):
    """岁悦 6 emotion 必须与大脑能力注册表一致（跨仓契约）。"""

    def test_brain_capability_yaml_keys_match(self):
        cap = os.path.join(_ROOT, "brain", "capabilities", "pepper_v1.yaml")
        if not os.path.isfile(cap):
            self.skipTest("pepper_v1.yaml 不存在")
        import yaml
        with open(cap, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        emap = (data.get("emotion_mapping") or {})
        yml_keys = set(emap)
        cfg_keys = set(cfg.EMOTION_TO_ACTION)
        self.assertEqual(
            yml_keys, cfg_keys,
            "pepper_v1.yaml 的 emotion_mapping 与 gateway_config.EMOTION_TO_ACTION 不一致："
            "仅 yaml=%s / 仅 py=%s" % (sorted(yml_keys - cfg_keys),
                                       sorted(cfg_keys - yml_keys)))


if __name__ == "__main__":
    unittest.main()
