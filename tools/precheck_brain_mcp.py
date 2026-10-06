"""A3 预检：验证大脑 MCP 侧可供 xiaozhi overlay 消费（不依赖 4090 / 真机 / xiaozhi server）。

做三件事：
  1. 列工具清单，并**交叉校验场景包 agent 声明的 tools 是否真的已注册**——
     这是N1（"8 个工具未注册却被场景包声明"）的守门人。
  2. 打印 `get_scene` 返回体的关键字段路径，供overlay X3 渲染 prompt 时对照。
  3. 校验 loader 的工具过滤是否生效：`agents[].tools` 必须是注册表的子集，
     未注册的一律落在 `tools_pending`（不下发给 LLM）。

判定规则（v2，2026-10-06）：
  - `tools` 里出现未注册工具      -> FAIL（exit 1），说明有人在 tools 里写了没建的工具
  - `tools_pending` 非空         -> PASS（exit 0），这是**预期状态**（路线图意图，已有专门字段承载）
  - `tool_visibility.filtered`   -> 必须为 True，否则 FAIL（消费方会拿到未过滤的工具集）

用法：
    python suiyue/tools/precheck_brain_mcp.py
    python suiyue/tools/precheck_brain_mcp.py --strict-plan
        --strict-plan：把 tools_pending 非空也视为 FAIL（用于"路线图必须清空"的发布纪律）

退出码：0 = 通过；1 = 有未注册工具被暴露（需处理后再上 overlay）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from brain.mcp.server import SuiyueMCPServer  # noqa: E402

# 场景包里 tools 允许出现的前缀白名单。
# 与 MCP-CONTRACT §8 决策 D-E 一致：云端只收敛 self.suiyue.* / self.daliang.*，
# self.pepper.* 归端侧 EMOTION_TO_ACTION（建云端工具面会双驱动，G6 暂不建）。
ALLOWED_PREFIXES = ("self.suiyue.", "self.daliang.")


def payload(res: dict):
    return json.loads(res["content"][0]["text"])


async def main() -> int:
    strict_plan = "--strict-plan" in sys.argv

    devices = [
        {"device_id": "pepper-01", "model": "pepper_v1", "provider": "static"},
    ]
    srv = SuiyueMCPServer()
    await srv.setup({"devices": devices})
    registered = [t["name"] for t in await srv.list_tools()]
    reg_set = set(registered)

    print("=== 1) 大脑 MCP 已注册工具 (%d) ===" % len(registered))
    for n in registered:
        print("  ", n)

    print("\n=== 2) get_scene(pepper-01) 关键字段 ===")
    res = await srv.call_tool("self.suiyue.get_scene", {"device_id": "pepper-01"})
    if res.get("isError"):
        print("  错误:", payload(res))
        return 1
    sc = payload(res)
    p = sc.get("persona", {}) or {}
    pp = p.get("persona", {}) or {}          # 双层嵌套，勿写成 p["name"]
    print("  scene_pack          :", sc["scene_pack"])
    print("  persona.persona.name:", pp.get("name"))
    print("  persona.persona.tone:", (pp.get("tone") or "")[:50])
    print("  agents              :", [a["name"] for a in sc.get("agents", [])])
    print("  safety.hard_rules   :", len((sc.get("safety") or {}).get("hard_rules") or []))
    tv = sc.get("tool_visibility") or {}
    print("  tool_visibility     : filtered=%s registered=%s exposed=%s pending=%s"
          % (tv.get("filtered"), tv.get("registered_count"),
             tv.get("exposed_count"), tv.get("pending_count")))

    print("\n=== 3) 交叉校验：agents[].tools（会下发给 LLM）===")
    errors: list[str] = []
    pendings: list[tuple] = []
    for a in sc.get("agents", []) or []:
        for t in a.get("tools") or []:
            ok = t in reg_set
            allowed = t.startswith(ALLOWED_PREFIXES)
            flag = "OK" if ok else "未注册!"
            if not allowed:
                flag += " 前缀越权"
            print("  %-10s %-32s %s" % (a["name"], t, flag))
            if not ok or not allowed:
                errors.append("%s -> %s（%s）" % (
                    a["name"], t,
                    "、".join(x for x in (
                        "" if ok else "大脑未注册",
                        "" if allowed else "前缀不在白名单 %s" % (ALLOWED_PREFIXES,),
                    ) if x)))
        for t in a.get("tools_pending") or []:
            pendings.append((a["name"], t))
            print("  %-10s %-32s PENDING(预期不下发)" % (a["name"], t))

    print("\n=== 4) 结论 ===")
    if not tv.get("filtered"):
        print("  FAIL: tool_visibility.filtered=False —— 本次 get_scene 未过滤工具，"
              "消费方拿到的是未过滤清单。")
        return 1
    if errors:
        print("  FAIL: 有 %d 个工具会被下发给 LLM 但大脑未注册/越权：" % len(errors))
        for e in errors:
            print("    - %s" % e)
        print("\n  修法：把这些工具从场景包 agent 的 `tools:` 移到 `planned_tools:`。")
        return 1
    if pendings:
        print("  PASS: 下发给 LLM 的工具全部已注册（0 越权）。")
        print("  路线图待建工具 %d 个，已隔离在 tools_pending，不会下发："
              % len(pendings))
        for an, t in pendings:
            print("    - %s -> %s" % (an, t))
        if strict_plan:
            print("\n  FAIL(--strict-plan)：要求路线图清空，但仍有 planned_tools。")
            return 1
    else:
        print("  PASS: 下发给 LLM 的工具全部已注册，且无待建工具。")
    print("\n  可安全执行 overlay X1/X2/X3。")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))