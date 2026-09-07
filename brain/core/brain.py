"""SuiyueBrain：云端统一意图分发中枢。

把"一个大脑三个身体"在云端落地：
- 每个在线设备以 device_id 注册，绑定一个 BodyProvider（真实或模拟）；
- 收到一个 `self.suiyue.emote` 意图后，按设备各自的能力注册表翻译成不同具体反应；
- 同一句话，otto / reachy / daliang 给出三种不同的、各自合理的表达与动作。

设计要点（MCP-CONTRACT §1 / §6）：
- 云端只下发 {emotion, intensity, action_primitive?}，不指定具体动作名；
- 本体无移动能力时，移动原语静默降级（degraded=True），不报错打断对话。
"""
from __future__ import annotations

from typing import Optional

from .provider import BodyProvider, EmoteResult, StaticProvider


class SuiyueBrain:
    def __init__(self) -> None:
        self._devices: dict[str, tuple[str, BodyProvider]] = {}

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
        """把同一意图广播给所有已注册设备（"一句话三种反应"演示入口）。"""
        out: dict[str, EmoteResult] = {}
        for did in self._devices:
            out[did] = await self.dispatch_emote(did, intent)
        return out

    async def handle_event(self, device_id: str, ev: dict):
        """把某设备的事件交给其 provider 翻译为对话上下文。"""
        provider = self.get_provider(device_id)
        return await provider.handle_event(ev)
