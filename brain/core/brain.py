"""SuiyueBrain：云端统一意图分发中枢。

把"一个大脑四个身体"在云端落地：
- 每个在线设备以 device_id 注册，绑定一个 BodyProvider（真实或模拟）；
- 收到一个 `self.suiyue.emote` 意图后，按设备各自的能力注册表翻译成不同具体反应；
- 同一句话，otto / reachy / daliang 给出三种不同的、各自合理的表达与动作。

设计要点（MCP-CONTRACT §1 / §6）：
- 云端只下发 {emotion, intensity, action_primitive?}，不指定具体动作名；
- 本体无移动能力时，移动原语静默降级（degraded=True），不报错打断对话。
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from .provider import BodyProvider, EmoteResult, StaticProvider
from ..packs.loader import DEFAULT_SCENE, ResolvedPack, load_resolved, select_by_model

log = logging.getLogger("suiyue.brain")


class SuiyueBrain:
    def __init__(self) -> None:
        self._devices: dict[str, tuple[str, BodyProvider]] = {}
        self.default_scene: str = DEFAULT_SCENE  # 未匹配模型/ PoC 演示回退（ADR-012 D4）
        self._scene_cache: dict[str, Optional[ResolvedPack]] = {}  # key = scene 或 model

    def register(self, device_id: str, model: str, provider: Optional[BodyProvider] = None) -> BodyProvider:
        """注册一个设备。

        - provider=None 时，按 model 自动创建 `StaticProvider`（模拟固件）；
        - 已接入真机的本体（如大亮）传入对应实时 provider。
        """
        if provider is None:
            provider = StaticProvider(model, device_id)
        self._devices[device_id] = (model, provider)
        return provider

    @property
    def device_ids(self) -> list[str]:
        return list(self._devices.keys())

    def get_provider(self, device_id: str) -> BodyProvider:
        if device_id not in self._devices:
            raise KeyError(f"未知设备: {device_id}（已注册: {self.device_ids}）")
        return self._devices[device_id][1]

    async def dispatch_emote(self, device_id: str, intent: dict) -> EmoteResult:
        """把意图下发给单个设备，返回其具体反应。"""
        provider = self.get_provider(device_id)
        return await provider.emote(intent)

    async def dispatch_emote_all(self, intent: dict) -> dict[str, EmoteResult]:
        """把同一意图广播给所有已注册设备（"一句话四种反应"演示入口）。"""
        out: dict[str, EmoteResult] = {}
        for did in self._devices:
            out[did] = await self.dispatch_emote(did, intent)
        return out

    async def handle_event(self, device_id: str, ev: dict):
        """把某设备的事件交给其 provider 翻译为对话上下文。"""
        provider = self.get_provider(device_id)
        return await provider.handle_event(ev)

    # ---------------- 场景包选择（G5 / ADR-012）----------------
    def scene_for(self, device_id: str, scene: Optional[str] = None):
        """返回某设备的已选场景包（ResolvedPack），未匹配则回退 default_scene。

        解析优先级（从高到低）：
        1. 显式 scene（会话参数，如 xiaozhi server 传 scene=pepper_cn_v1）；
        2. device_model 匹配（能力注册表的 model → select_by_model）；
        3. default_scene（建议 elder_cn_v1）。
        结果按 key（scene 或 model）缓存，模型不变则不重算。
        """
        if device_id not in self._devices:
            return None
        model = self._devices[device_id][0]
        key = scene or model
        if key in self._scene_cache:
            return self._scene_cache[key]
        pack_id = scene or select_by_model(model) or self.default_scene
        try:
            rp = load_resolved(pack_id)
        except Exception as e:  # 包损坏/缺失：降级到 default，不崩大脑
            log.warning("场景包加载失败(%s)：%s，回退 %s", pack_id, e, self.default_scene)
            rp = load_resolved(self.default_scene)
        self._scene_cache[key] = rp
        return rp

    def get_scene(self, device_id: str, scene: Optional[str] = None,
                  available_tools: Optional[Iterable[str]] = None) -> Optional[dict]:
        """返回 MCP-CONTRACT §8 `self.suiyue.get_scene` 的契约体（dict）。

        `available_tools`：本进程 MCP server 实际注册的工具名集合。传入后
        场景包里的工具会被过滤（未注册的落到 `tools_pending`，不下发给 LLM），
        见 `ResolvedPack.to_scene_payload`。省略则不过滤（仅供纯单测）。
        """
        rp = self.scene_for(device_id, scene)
        return rp.to_scene_payload(available_tools) if rp else None
