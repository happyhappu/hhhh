"""本体提供方：把 `self.suiyue.emote` 意图解析成本体的具体反应。

- `StaticProvider`：仅依据能力注册表解析意图（不真正执行）。用于 otto / reachy
  在尚未接入真机时的演示、测试；也用于"能力完整性"校验。
- `DaliangProvider`：包 `brain.daliang_provider.DaliangOrchestrator`，实时驱动大亮底盘。

两者都返回 `EmoteResult`，使大脑侧无需关心底层是模拟还是真机——这正是
MCP-CONTRACT §1「云端无权指定具体动作名，端侧按能力注册表决定」的云端镜像。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional

from .capability import load_capability


@dataclass
class EmoteResult:
    """一次 emote 意图在某本体上的解析/执行结果。"""

    device_id: str
    device_model: str
    expression: dict                 # 本体专属表情/姿态（otto 动作集 / reachy 头-天线-眼 / daliang 委派）
    motion: Optional[dict] = None    # {"primitive","params"} 或 None（无移动意图/无移动能力）
    degraded: bool = False           # 移动原语因本体无能力被降级忽略
    executed: bool = False           # 是否真实下发执行（Static=False；Daliang 有底盘意图=True）
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class BodyProvider:
    """所有本体的统一接口。"""

    device_model: str = "unknown"
    device_id: str = "unknown"

    async def emote(self, intent: dict) -> EmoteResult:
        raise NotImplementedError

    async def handle_event(self, ev: dict) -> Optional[dict]:
        """底盘/传感事件 → 对话上下文 nudge。默认不处理。"""
        return None


def _resolve_motion(model_cap: dict, intent: dict, *, static: bool) -> tuple[Optional[dict], bool, str]:
    """判断移动原语是否可执行。

    返回 (motion, degraded, note)。
    - 本体有 `locomotion: chassis`（仅 daliang）→ 原语可解析为底盘命令；
    - 其余本体（otto/reachy 无该字段）→ 移动原语安全降级忽略（MCP-CONTRACT §6）。
    """
    primitive = (intent.get("action_primitive") or "").lower()
    if not primitive:
        return None, False, ""
    if model_cap.get("locomotion") == "chassis":
        note = "" if not static else "[static] 底盘意图已解析，未连接真实底盘（演示用）"
        return {"primitive": primitive, "params": intent.get("params", {})}, False, note
    return (
        None,
        True,
        f"{model_cap.get('device_model')} 无移动能力，动作原语 '{primitive}' 已降级忽略（安全优先）",
    )


def _expression_of(model_cap: dict, emotion: str) -> dict:
    """取本体的表情/姿态映射。表现层被阻塞的本体（daliang）返回委派说明。"""
    emap = model_cap.get("emotion_mapping", {})
    expr = emap.get(emotion, emap.get("neutral", {})) or {}
    if str(model_cap.get("expression", {}).get("status", "")).startswith("blocked"):
        # 大亮表现层待尽调：表情交给 companion-app，仅保留情感-运动语义提示
        return {"delegated_to": "companion-app", "semantic_motion": expr.get("motion")}
    return expr


class StaticProvider(BodyProvider):
    """模拟端侧固件：仅按能力注册表解析意图，不真正执行。

    用于 otto / reachy 在尚未烧录固件时的演示与单测，以及能力完整性校验。
    """

    def __init__(self, model: str, device_id: Optional[str] = None):
        self.device_model = model
        self.device_id = device_id or model
        self.cap = load_capability(model)

    async def emote(self, intent: dict) -> EmoteResult:
        emotion = intent.get("emotion", "neutral")
        expression = _expression_of(self.cap, emotion)
        motion, degraded, note = _resolve_motion(self.cap, intent, static=True)
        return EmoteResult(
            device_id=self.device_id,
            device_model=self.device_model,
            expression=expression,
            motion=motion,
            degraded=degraded,
            executed=False,
            note=note or "static simulation（模拟固件，不真正执行）",
        )


class DaliangProvider(BodyProvider):
    """大亮实时提供方：包 DaliangOrchestrator，真实驱动底盘。"""

    def __init__(self, orchestrator: Any, device_id: str = "daliang-01"):
        from ..daliang_provider.orchestrator import DaliangOrchestrator

        if not isinstance(orchestrator, DaliangOrchestrator):
            raise TypeError("DaliangProvider 需要 DaliangOrchestrator 实例")
        self.device_model = "daliang_v1"
        self.device_id = device_id
        self.orch = orchestrator

    async def emote(self, intent: dict) -> EmoteResult:
        res = await self.orch.execute_intent(intent)
        primitive = (intent.get("action_primitive") or "").lower()
        motion = None
        executed = False
        if primitive:
            motion = {"primitive": primitive, "params": intent.get("params", {})}
            executed = True
        expression = {"delegated_to": "companion-app"}
        note = str(res.get("reason") or res.get("message") or "")
        return EmoteResult(
            device_id=self.device_id,
            device_model=self.device_model,
            expression=expression,
            motion=motion,
            degraded=False,
            executed=executed,
            note=note,
        )

    async def handle_event(self, ev: dict) -> Optional[dict]:
        return self.orch.handle_event(ev)
