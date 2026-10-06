"""overlay X3 场景包注入器测试（无需 4090 / 无需真机 / 无需 xiaozhi server 实际运行）。

用真实的 stdio MCP 调用大脑 `self.suiyue.get_scene`，验证：
  1. 能真的拉到场景包（stdio 链路通）
  2. `render_scene_prompt` 字段路径正确（尤其**双层嵌套** persona）
  3. 注入文本**不含** tools 清单与 emotion_calibration（N1 硬约束）
  4. 缓存生效（第二次瞬时返回）
  5. 失败降级正确（大脑不可用时返回空串，绝不抛异常）

运行：
    python suiyue/overlay/test_suiyue_scene.py
    python -m unittest overlay.test_suiyue_scene -v
"""
from __future__ import annotations

import os
import sys
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SUIYUE = os.path.dirname(_HERE)
for p in (_SUIYUE, _HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

from suiyue_scene import (  # noqa: E402
    build_base_prompt, inject_scene_into_prompt, render_scene_prompt,
)

REPO = _SUIYUE
GOOD_CFG = {"suiyue": {"device_id": "pepper-01",
                       "brain_mcp_enabled": True,
                       "brain_repo": REPO}}


class TestRenderScenePrompt(unittest.TestCase):
    """纯函数测试：用真实 get_scene 返回体做输入，不需要 MCP。"""

    @classmethod
    def setUpClass(cls) -> None:
        import asyncio
        from suiyue_scene import _fetch_scene_via_stdio
        cls.scene = asyncio.run(_fetch_scene_via_stdio(GOOD_CFG, "pepper-01"))

    def test_scene_fetched(self):
        self.assertIsInstance(self.scene, dict)
        self.assertEqual(self.scene["scene_pack"], "pepper_cn_v1")

    def test_double_nested_persona_path(self):
        """persona 是双层嵌套：scene['persona']['persona']['name']。"""
        inner = self.scene["persona"]["persona"]
        self.assertEqual(inner["name"], "岁悦")
        rendered = render_scene_prompt(self.scene)
        self.assertIn("岁悦", rendered)

    def test_render_contains_key_sections(self):
        r = render_scene_prompt(self.scene)
        self.assertIn("pepper_cn_v1", r)
        self.assertIn("companion", r)
        self.assertIn("health", r)
        self.assertIn("硬规则", r)

    def test_render_excludes_tools_and_emotion(self):
        """N1 硬约束：不得注入 tools 清单与emotion_calibration。"""
        r = render_scene_prompt(self.scene)
        self.assertNotIn("self.pepper.", r)
        self.assertNotIn("profile.get", r)
        self.assertNotIn("knowledge.rag_search", r)
        self.assertNotIn("approach_and_wave", r)   # emotion_calibration 的 motion

    def test_scene_tools_are_registry_subset(self):
        """大脑侧过滤生效：get_scene 返回的 tools 必须是已注册工具的子集。"""
        tv = self.scene.get("tool_visibility") or {}
        self.assertTrue(tv.get("filtered"), "get_scene 未过滤工具")
        reg = set(tv.get("registered_tools") or [])
        self.assertIn("self.suiyue.emote", reg)
        for a in self.scene["agents"]:
            for t in a["tools"]:
                self.assertIn(t, reg, "下发了未注册工具: %s" % t)

    def test_pending_tools_not_in_rendered_prompt(self):
        """tools_pending 里的工具绝不能出现在注入文本中。"""
        r = render_scene_prompt(self.scene)
        for a in self.scene["agents"]:
            for t in a.get("tools_pending") or []:
                self.assertNotIn(t, r, "pending 工具泄漏进 prompt: %s" % t)
        # 确认确实有 pending 工具（否则本测试是空转）
        n = sum(len(a.get("tools_pending") or []) for a in self.scene["agents"])
        self.assertGreater(n, 0, "场景包已无 pending 工具，请同步更新本测试")

    def test_render_handles_bad_input(self):
        self.assertEqual(render_scene_prompt({}), "")
        self.assertEqual(render_scene_prompt(None), "")

    def test_render_includes_expression_contract(self):
        """1.3：必须把「什么情绪用什么 emoji」告诉 LLM。

        否则云端 get_emotion() 扫不到 emoji -> 恒 neutral -> Pepper 恒静默。
        """
        expr = self.scene["persona"].get("expression") or {}
        self.assertTrue(expr.get("emoji_map"), "场景包缺少 expression.emoji_map")
        r = render_scene_prompt(self.scene)
        self.assertIn("情绪表达", r)
        for emo, emoji in expr["emoji_map"].items():
            self.assertIn(emoji, r, "prompt里缺少 %s 的 emoji %s" % (emo, emoji))
        self.assertIn(expr["fallback_emoji"], r)

    def test_expression_emoji_subset_of_upstream_map(self):
        """注入的 emoji 必须是云端 EMOJI_MAP 认的，否则被静默忽略。

        云端 EMOJI_MAP 见 v0.9.7 core/utils/textUtils.py:8-30；
        这里用同文件 pepper/test_emotion_contract.py 的权威副本。
        """
        from pepper.test_emotion_contract import UPSTREAM_EMOJI_MAP
        expr = self.scene["persona"].get("expression") or {}
        emap = dict(expr.get("emoji_map") or {})
        if expr.get("fallback_emoji"):
            emap["__fallback__"] = expr["fallback_emoji"]  # 兜底 emoji 也要合法
        for emo, emoji in emap.items():
            self.assertIn(emoji, UPSTREAM_EMOJI_MAP,
                          "云端不认识的 emoji：%s=%s（会被静默忽略）" % (emo, emoji))


class TestInjectScene(unittest.TestCase):
    """注入器行为测试（含真实 stdio 一次，约 13s，故单独标注）。"""

    def test_inject_and_cache(self):
        t0 = time.perf_counter()
        first = inject_scene_into_prompt(GOOD_CFG, "pepper-01")
        t1 = time.perf_counter()
        self.assertTrue(first, "首次注入应拿到场景包文本")
        self.assertIn("岁悦", first)

        t2 = time.perf_counter()
        second = inject_scene_into_prompt(GOOD_CFG, "pepper-01")
        t3 = time.perf_counter()
        self.assertEqual(first, second, "缓存命中应返回同样内容")
        self.assertLess(t3 - t2, 1.0, "缓存命中应<1s（实际 %.3fs）" % (t3 - t2))
        print("\n    首次 %.1fs / 缓存 %.4fs" % (t1 - t0, t3 - t2))

    def test_degrade_when_brain_unavailable(self):
        """大脑不可用时必须返回空串（上游保留原 prompt），不得抛异常。"""
        bad = {"suiyue": {"device_id": "pepper-99",   # 换 id -> 避开缓存
                          "brain_mcp_enabled": True,
                          "brain_repo": r"D:\不存在的路径xyz"}}
        self.assertEqual(inject_scene_into_prompt(bad, "pepper-99"), "")

    def test_no_suiyue_section(self):
        self.assertEqual(inject_scene_into_prompt({"selected_module": {}}, "x"), "")


class TestBuildBasePrompt(unittest.TestCase):
    def test_merge_order(self):
        merged = build_base_prompt("原始 base", "场景文本")
        self.assertTrue(merged.startswith("场景文本"))
        self.assertIn("原始 base", merged)

    def test_empty_scene_keeps_original(self):
        self.assertEqual(build_base_prompt("原始 base", ""), "原始 base")

    def test_empty_original_returns_scene(self):
        self.assertEqual(build_base_prompt("", "场景"), "场景")


if __name__ == "__main__":
    unittest.main(verbosity=2)
