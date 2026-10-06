"""场景包加载器单测（G5，ADR-012）。

运行：
    python -m brain.packs.test_loader        # 在 suiyue/ 根目录
    python suiyue/brain/packs/test_loader.py  # 或绝对路径

验证核心契约：pepper_cn_v1 继承合并后 = elder 域 + pepper 物理/companion。
"""
from __future__ import annotations

import os
import sys

# 让脚本能 import brain 包（仓库根 = suiyue 的父目录）
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from brain.packs.loader import (  # noqa: E402
    DEFAULT_SCENE,
    discover_packs,
    load_resolved,
    select_by_model,
)


def _assert(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(f"FAIL: {msg}")
    print(f"  ✓ {msg}")


def test_discover() -> None:
    print("[discover_packs]")
    packs = discover_packs()
    for p in ("elder_cn_v1", "kids_v1", "pepper_cn_v1"):
        _assert(p in packs, f"已发现场景包 {p}")


def test_pepper_inheritance() -> None:
    print("[pepper_cn_v1 继承合并 = elder 域 + pepper 物理/companion]")
    rp = load_resolved("pepper_cn_v1")

    # 1) manifest 正确传递
    _assert(rp.manifest["scene_pack"] == "pepper_cn_v1", "manifest.scene_pack == pepper_cn_v1")
    _assert(rp.manifest["device_model"] == "pepper_v1", "manifest.device_model == pepper_v1")
    _assert(rp.manifest["inherits"] == "elder_cn_v1", "manifest.inherits == elder_cn_v1")

    # 2) persona：pepper 覆盖 voice，继承 elder 的 tone（dict 深合并子胜父）
    persona = rp.persona.get("persona", {})
    _assert(persona.get("voice") == "warm_female_elder", "persona.voice 被 pepper 覆盖")
    _assert("温和" in persona.get("tone", ""), "persona.tone 继承自 elder")

    # 3) safety：保留 elder 的 hard_rules（4 条）+ 并入 pepper 的 physical 层
    safety = rp.safety or {}
    _assert(len(safety.get("hard_rules", [])) == 4, "safety.hard_rules 继承 elder 的 4 条")
    _assert(safety.get("physical", {}).get("speed_limit_mps") == 0.4,
            "safety.physical 由 pepper 新增并入（限速 0.4）")
    _assert(safety.get("physical", {}).get("autonomous_life") == "disabled",
            "safety.physical.autonomous_life == disabled（禁用 ALAutonomousLife）")

    # 4) agents：elder 的 health + pepper 的 companion 并集
    _assert(set(rp.agents.keys()) == {"health", "companion"},
            "agents = {health, companion} 并集")

    # 5) mobility / physical_caps：仅 pepper 有
    _assert(rp.mobility is not None and "geofence" in rp.mobility, "mobility 来自 pepper")
    _assert(rp.physical_caps is not None and rp.physical_caps.get("dof") == 20,
            "physical_caps.dof == 20")

    # 6) emotion_calibration：合并（elder 3 项 + pepper 新增 → 6 项）
    cal = rp.persona.get("emotion_calibration", {})
    _assert(set(cal.keys()) == {"happy", "soothing", "concerned", "curious", "excited", "neutral"},
            "emotion_calibration 合并为 6 项（含 pepper 的 curious/excited/neutral）")
    _assert(cal["happy"].get("motion") == "approach_and_wave",
            "pepper 的 emotion→motion 字段生效")


def test_elder_standalone() -> None:
    print("[elder_cn_v1 独立包]")
    rp = load_resolved("elder_cn_v1")
    _assert(rp.agents.keys() == {"health"}, "elder agents 仅 health")
    _assert(rp.safety is not None and "physical" not in rp.safety,
            "elder 无 Pepper 物理安全层")
    _assert(rp.mobility is None, "elder 无 mobility")
    _assert(rp.manifest.get("device_model") is None, "elder 未声明 device_model（纯域包）")


def test_kids_compat() -> None:
    print("[kids_v1 PoC 包兼容（scene.yaml + inline safety）]")
    rp = load_resolved("kids_v1")
    _assert(rp.manifest["scene_pack"] == "kids_v1", "kids manifest.scene_pack == kids_v1")
    # inline safety 被提升到 safety section（loader 兼容两种根文件）
    _assert(rp.safety is not None and len(rp.safety.get("hard_rules", [])) == 3,
            "kids inline safety 被提升到 section")
    _assert(rp.agents == {}, "kids 无 agents/ 目录（PoC 豁免）")


def test_select_and_payload() -> None:
    print("[select_by_model + to_scene_payload 契约体]")
    # device_model 匹配
    _assert(select_by_model("pepper_v1") == "pepper_cn_v1",
            "select_by_model(pepper_v1) == pepper_cn_v1")
    _assert(select_by_model("otto_v1") is None, "select_by_model(otto_v1) == None（无包→回退 default）")

    # payload 结构
    rp = load_resolved("pepper_cn_v1")
    payload = rp.to_scene_payload()
    _assert(payload["scene_pack"] == "pepper_cn_v1", "payload.scene_pack 正确")
    _assert(len(payload["agents"]) == 2, "payload.agents 含 2 个启用 Agent")
    _assert(payload["safety"]["disclaimer"], "payload.safety.disclaimer 非空")
    _assert(payload["emotion_calibration"], "payload.emotion_calibration 非空")
    # default 回退常量
    _assert(DEFAULT_SCENE == "elder_cn_v1", "DEFAULT_SCENE == elder_cn_v1")


# --------------------------------------------------------------------------
# N1 修复：工具过滤（unittest 风格，保证被 CI 的 unittest discover 抓到）
# --------------------------------------------------------------------------
import unittest  # noqa: E402

# 与 brain/mcp 实际注册表保持一致的最小集（此处只测loader 逻辑，不需要全量）
_REG = {"self.suiyue.emote", "self.suiyue.get_scene",
        "self.suiyue.list_devices", "self.suiyue.poll_events",
        "self.daliang.navigate", "self.daliang.stop_all"}


class TestToolFiltering(unittest.TestCase):
    """`to_scene_payload(available_tools=...)` 把未注册工具隔离到 tools_pending。"""

    def test_pending_tools_not_in_tools(self):
        payload = load_resolved("pepper_cn_v1").to_scene_payload(_REG)
        by_name = {a["name"]: a for a in payload["agents"]}
        self.assertEqual(set(by_name), {"companion", "health"})

        # companion：Pepper 专属工具全在 pending
        comp = by_name["companion"]
        self.assertNotIn("self.pepper.approach", comp["tools"])
        for t in ("self.pepper.approach", "self.pepper.tablet_render",
                  "self.pepper.stop_all"):
            self.assertIn(t, comp["tools_pending"])
        self.assertIn("self.suiyue.emote", comp["tools"])

        # health：记忆/知识库工具全在 pending
        hp = by_name["health"]
        for t in ("profile.get", "knowledge.rag_search"):
            self.assertNotIn(t, hp["tools"])
            self.assertIn(t, hp["tools_pending"])
        self.assertIn("self.suiyue.emote", hp["tools"])

    def test_tools_subset_of_registry(self):
        """核心不变式：下发给 LLM 的工具必须是注册表的子集。"""
        payload = load_resolved("pepper_cn_v1").to_scene_payload(_REG)
        for a in payload["agents"]:
            for t in a["tools"]:
                self.assertIn(t, _REG, "tools 里出现了未注册工具: %s" % t)

    def test_tool_visibility_counts(self):
        payload = load_resolved("pepper_cn_v1").to_scene_payload(_REG)
        tv = payload["tool_visibility"]
        self.assertTrue(tv["filtered"])
        self.assertEqual(tv["registered_count"], len(_REG))
        # companion + health 各1 个已注册工具
        self.assertEqual(tv["exposed_count"], 2)
        self.assertGreater(tv["pending_count"], 0)

    def test_no_filter_keeps_declared_and_marks_unfiltered(self):
        """省略 available_tools = 不过滤（老调用方兼容），但 filtered 必须为 False。"""
        payload = load_resolved("pepper_cn_v1").to_scene_payload()
        tv = payload["tool_visibility"]
        self.assertFalse(tv["filtered"])
        self.assertIsNone(tv["registered_count"])

    def test_registry_filter_is_case_sensitive_and_exact(self):
        """注册表里没有的工具就是不下发，不做前缀/模糊匹配。"""
        payload = load_resolved("pepper_cn_v1").to_scene_payload(set())
        by_name = {a["name"]: a for a in payload["agents"]}
        for a in payload["agents"]:
            self.assertEqual(a["tools"], [], "空注册表时不应暴露任何工具")
            # 声明过但未注册的一律进 pending
            self.assertIn("self.suiyue.emote", a["tools_pending"])
        for t in ("self.pepper.stop_all", "profile.get", "knowledge.rag_search"):
            self.assertIn(t, by_name["companion"]["tools_pending"])
        for t in ("profile.get", "knowledge.rag_search"):
            self.assertIn(t, by_name["health"]["tools_pending"])

    def test_planned_tools_dedup(self):
        """同一工具既在 tools 又在 planned_tools 时不重复。"""
        rp = load_resolved("pepper_cn_v1")
        for a in rp.agents.values():
            a["tools"] = list(a.get("tools") or []) + ["self.suiyue.emote"]
        payload = rp.to_scene_payload(_REG)
        for a in payload["agents"]:
            self.assertEqual(len(a["tools"]), len(set(a["tools"])))
            self.assertEqual(len(a["tools_pending"]), len(set(a["tools_pending"])))


if __name__ == "__main__":
    test_discover()
    test_pepper_inheritance()
    test_elder_standalone()
    test_kids_compat()
    test_select_and_payload()
    print("\n全部场景包加载器单测通过 ✅")
