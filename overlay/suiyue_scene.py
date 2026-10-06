"""岁悦 X3 · 场景包注入器（放在 xiaozhi server 侧的被overlay 文件）。

作用：会话建立时调大脑 MCP 的 `self.suiyue.get_scene(device_id)`，
把返回的场景内容（persona 语气 + agent system_prompt + safety 硬规则）
渲染成一段文本，交给 `prompt_manager` 注入 system prompt。

设计要点（对齐 GET_SCENE_OVERLAY_GUIDE.md 与 XIAOZHI_SERVER_PATCHES.md）：
  - **纯新增文件**，不改上游任何逻辑；由 connection._init_prompt_enhancement 最小改动调用。
  - **失败即回退**：任何异常都不影响会话，退回上游原始 prompt。
  - **进程内缓存**：同一 device_id 只拉一次（决策 D-D）。
  - **不注入工具清单**：只注入 system_prompt 文本。场景包里声明的
    `self.pepper.*` / `profile.*` / `knowledge.*` 均未在大脑注册（N1），
    暴露给 LLM 会导致它调用不存在的工具而中断对话。
  - **字段路径**：返回体 persona 是双层嵌套 -> `scene["persona"]["persona"]["name"]`。
  - `emotion_calibration` 不进 prompt（端侧 emotion->motion 曲线，与 LLM 文本无关）。
  - `persona.expression` **进** prompt（2026-10-06 新增）：云端 `get_emotion()`
    靠扫描 LLM 回复里的第一个 emoji 判定情绪，LLM 不吐 emoji 则恒 `neutral`、
    本体恒静默不动，故必须显式给出"什么情绪用什么 emoji"。

被上游调用示例（connection.py::_init_prompt_enhancement）：
    from suiyue_scene import inject_scene_into_prompt
    base = inject_scene_into_prompt(self.config, self.device_id, self.logger)
    enhanced = self.prompt_manager.build_enhanced_prompt(
        base, self.device_id, self.client_ip,
        emoji_enabled=(self.features or {}).get("emoji", True))
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
from typing import Any, Dict, Optional

# 进程内缓存：{device_id: (rendered_text, expire_ts)}
_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = threading.Lock()
CACHE_TTL_S = 300.0          # 决策 D-D：缓存 5 分钟

# 超时说明（实测 2026-10-06）：首次 stdio 调大脑 MCP 需拉起子进程 + 加载场景包，
# 实测约 13s（其中含大亮底盘连接超时重试）。**会话建立时同步等13s不可接受**，
# 故：超时要给足，且提供后台预热（warmup）让首个真实会话不被拖慢。
MCP_TIMEOUT_S = 30.0


def _log(logger, level: str, msg: str) -> None:
    try:
        if logger is not None:
            getattr(logger, level, logger.info)(msg)
    except Exception:
        pass


def render_scene_prompt(scene: Dict[str, Any]) -> str:
    """把 get_scene 返回体渲染成 prompt 文本片段。

    ⚠️ persona 是双层嵌套：真实字段在 scene["persona"]["persona"]["name"]。
    """
    if not isinstance(scene, dict):
        return ""

    blocks = []

    pack = scene.get("scene_pack") or ""
    if pack:
        blocks.append("[岁悦场景包：%s]" % pack)

    persona = scene.get("persona") or {}
    inner = persona.get("persona") or {}          # 双层嵌套
    name = inner.get("name")
    if name:
        blocks.append("你是%s。" % name)
    address = inner.get("address")
    if address:
        blocks.append("称呼对方用「%s」。" % address)
    tone = inner.get("tone")
    if tone:
        blocks.append("语气：%s" % tone)
    rp = inner.get("repetition_policy")
    if rp:
        blocks.append("重复应对：%s" % rp)

    # 目标用户画像
    tu = persona.get("target_user") or {}
    if tu.get("profile"):
        blocks.append("服务对象：%s" % tu["profile"])

    # 适老化/开场等
    cui = persona.get("companion_ui") or {}
    if cui.get("tablet_greeting"):
        blocks.append("开场问候：%s" % cui["tablet_greeting"])

    # 各 Agent 的 system_prompt（只注入文本，不注入 tools）
    for ag in scene.get("agents") or []:
        sp = (ag.get("system_prompt") or "").strip()
        if sp:
            blocks.append("【%s】%s" % (ag.get("name") or "agent", sp))

    # 情绪表达契约（1.3 增强）
    # 云端 get_emotion() 靠"扫描 LLM 回复里的第一个 emoji"判定情绪，
    # 不吐 emoji -> 恒 neutral -> 本体恒静默不动。这段把映射显式告诉 LLM。
    expr = (persona.get("expression") or {})
    emap = expr.get("emoji_map") or {}
    if emap:
        pairs = "、".join("%s→%s" % (k, v) for k, v in emap.items())
        blocks.append(
            "【情绪表达】每轮回复**必须**以一个情绪 emoji 开头（只用下列，不要堆叠）：%s"
            % pairs)
        if expr.get("fallback_emoji"):
            blocks.append("不确定情绪时用 %s，不要省略 emoji。" % expr["fallback_emoji"])

    # 安全硬规则（护栏，必须在）
    safety = scene.get("safety") or {}
    rules = safety.get("hard_rules") or []
    if rules:
        blocks.append("【必须遵守的硬规则】")
        for r in rules:
            blocks.append("- %s" % r)
    disc = safety.get("disclaimer")
    if disc:
        blocks.append("免责说明：%s" % disc)

    # 注意：故意不渲染 emotion_calibration（端侧 emotion->motion 曲线）

    return "\n".join(blocks).strip()


async def _fetch_scene_via_stdio(config: Dict[str, Any],
                                 device_id: str) -> Optional[Dict[str, Any]]:
    """通过 stdio 调大脑 MCP 的 get_scene。

    依赖 mcp python sdk（上游 requirements 已含 mcp==1.22.0）。
    失败返回 None —— 调用方会回退原始 prompt。
    """
    sy = (config or {}).get("suiyue") or {}
    if not sy.get("brain_mcp_enabled", True):
        return None

    repo = sy.get("brain_repo") or os.environ.get(
        "SUIYUE_BRAIN_REPO", r"D:\WorkBuddy\桌面陪伴机器人\suiyue")
    mcp_cfg = os.path.join(repo, "brain", "mcp", "config.yaml")
    if not os.path.isfile(mcp_cfg):
        raise FileNotFoundError("大脑 MCP 配置不存在: %s" % mcp_cfg)

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(
        command="python" if os.name == "nt" else "python3",
        args=["-m", "brain.mcp", "--config", mcp_cfg],
        env=dict(os.environ, PYTHONPATH=repo),
    )
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as session:
            await session.initialize()
            res = await session.call_tool(
                "self.suiyue.get_scene", {"device_id": device_id})
            return _parse_tool_result(res)


def _parse_tool_result(res: Any) -> Optional[Dict[str, Any]]:
    """解析 call_tool 返回，兼容两种形态。

    - mcp SDK 的 `CallToolResult` **对象**：字段是 `is_error`（下划线）、
      `content` 为 `list[TextContent]`（TextContent.text）。
    - 朴素 dict：字段是 `isError`、`content` 为 `list[dict]`。

    踩坑记录：最初按 dict 解析导致 always返回 None（2026-10-06）。
    """
    # 形态 1：SDK 对象
    if hasattr(res, "content") and hasattr(res, "is_error"):
        if res.is_error:
            detail = ""
            if getattr(res, "content", None):
                first = res.content[0]
                detail = getattr(first, "text", "") or ""
            raise RuntimeError(detail or "get_scene 返回 is_error")
        if not res.content:
            return None
        text = getattr(res.content[0], "text", None)
        if not text:
            return None
        return json.loads(text)

    # 形态 2：朴素 dict
    if isinstance(res, dict):
        if res.get("isError"):
            content = res.get("content") or []
            raise RuntimeError(
                content[0].get("text") if content else "get_scene 返回 isError")
        content = res.get("content") or []
        if not content:
            return None
        text = content[0].get("text")
        if not text:
            return None
        return json.loads(text)

    raise TypeError("未知的 call_tool 返回类型: %r" % type(res))


def _cache_key(config: Dict[str, Any], device_id: str) -> str:
    """缓存键 = device_id + brain_repo 路径。

    踩坑记录：最初只用 device_id 做键，导致切换 brain_repo 后仍命中旧缓存
    （降级测试因此假失败，2026-10-06）。
    """
    repo = ""
    try:
        repo = ((config or {}).get("suiyue") or {}).get("brain_repo") or ""
    except Exception:
        pass
    return "%s@%s" % (device_id, repo)


def _get_cached(key: str) -> Optional[str]:
    with _CACHE_LOCK:
        item = _CACHE.get(key)
        if not item:
            return None
        text, expire = item
        if time.time() > expire:
            _CACHE.pop(key, None)
            return None
        return text


def _put_cache(key: str, text: str) -> None:
    with _CACHE_LOCK:
        _CACHE[key] = (text, time.time() + CACHE_TTL_S)


def warmup_async(config: Dict[str, Any], logger=None) -> None:
    """后台预热：server 启动时调用，把场景包拉进缓存。

    这样首个真实会话走`_get_cached` 命中，不用等 13s。
    用法（上游 app.py 启动处，可选）：
        threading.Thread(
            target=suiyue_scene.warmup, args=(config,), daemon=True).start()
    """
    try:
        sy = (config or {}).get("suiyue") or {}
        if not sy:
            return
        device_id = sy.get("device_id")
        if not device_id:
            return
        key = _cache_key(config, device_id)
        if _get_cached(key):
            return
        scene = asyncio.run(asyncio.wait_for(
            _fetch_scene_via_stdio(config, device_id), timeout=MCP_TIMEOUT_S))
        rendered = render_scene_prompt(scene or {})
        if rendered:
            _put_cache(key, rendered)
            _log(logger, "info", "[suiyue] 场景包预热完成 (%d 字符)" % len(rendered))
        else:
            _log(logger, "warning", "[suiyue] 场景包预热返回空")
    except Exception as exc:
        _log(logger, "warning", "[suiyue] 场景包预热失败（不影响启动）: %s" % exc)


def warmup(config: Dict[str, Any], logger=None) -> None:
    """warmup_async 的同步包装，供 threading.Thread 直接 target 使用。"""
    warmup_async(config, logger)


def inject_scene_into_prompt(config: Dict[str, Any], device_id: str,
                             logger=None) -> str:
    """给上游 `_init_prompt_enhancement` 用的同步入口。

    返回**注入后的 base prompt 文本**；失败时返回空串（调用方保留原 prompt）。
    绝不抛异常——overlay 不能影响会话可用性。
    """
    try:
        sy = (config or {}).get("suiyue") or {}
        if not sy:
            return ""
        target_id = sy.get("device_id") or device_id
        key = _cache_key(config, target_id)

        cached = _get_cached(key)
        if cached:
            _log(logger, "debug", "[suiyue] 场景包命中缓存: %s" % target_id)
            return cached

        try:
            scene = asyncio.run(asyncio.wait_for(
                _fetch_scene_via_stdio(config, target_id), timeout=MCP_TIMEOUT_S))
        except Exception as exc:
            _log(logger, "warning",
                 "[suiyue] 拉取场景包失败，回退原始 prompt: %s" % exc)
            return ""

        if not scene:
            return ""
        rendered = render_scene_prompt(scene)
        if not rendered:
            return ""
        _put_cache(key, rendered)
        _log(logger, "info",
             "[suiyue] 场景包已注入 (%s, %d 字符)"
             % (scene.get("scene_pack", "?"), len(rendered)))
        return rendered
    except Exception as exc:                     # 兜底：overlay 永不影响会话
        _log(logger, "error", "[suiyue] 注入异常: %s" % exc)
        return ""


def build_base_prompt(original: str, scene_text: str) -> str:
    """把场景文本与上游原始 base prompt 合并。

    场景文本放在**前面**：LLM 对prompt 开头更敏感，且上游模板的
    `<identity>{{base_prompt}}</identity>` 会把整段包进 identity 段。
    """
    if not scene_text:
        return original
    if not original:
        return scene_text
    return "%s\n\n%s" % (scene_text, original)
