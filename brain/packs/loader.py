"""场景包加载器（G5，ADR-012）。

负责"加载 + 选择 + 暴露"三件事中的前两件：
- 把 `brain/packs/<pack_id>/` 下的 YAML 读成结构化 `ResolvedPack`；
- 展开 `inherits` 继承链（目录并集 + 文件级深合并，子包胜父包）；

选择（按 device_id 选哪个包）挂在 `SuiyueBrain.scene_for`，本模块只提供纯函数。

约定（ADR-012 §1）：
- 完整包根文件 `persona.yaml` 顶层带 manifest（scene_pack/version/device_model/inherits/status）；
- PoC 包（kids_v1）根文件 `scene.yaml` 也带上述字段（§5 豁免标准化）；
- 其余 section 文件：safety.yaml / mobility.yaml / physical_caps.yaml（顶层键名同 section）；
- agents/ 下每个 YAML 一个 Agent（键名取文件内 `agent` 字段或文件名）。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import yaml

PACKS_DIR = os.path.dirname(os.path.abspath(__file__))

# manifest 元信息键（从根文件顶层抽取，其余归 persona section）
MANIFEST_KEYS = ("scene_pack", "version", "device_model", "inherits", "status")

# 未显式匹配模型 / PoC 演示时的回退包（ADR-012 D4）
DEFAULT_SCENE = "elder_cn_v1"

# section -> 文件名
_SECTION_FILES = {
    "safety": "safety.yaml",
    "mobility": "mobility.yaml",
    "physical_caps": "physical_caps.yaml",
}

# 根文件候选（先 persona.yaml，后 PoC 的 scene.yaml）
_ROOT_CANDIDATES = ("persona.yaml", "scene.yaml")


@dataclass
class ResolvedPack:
    """继承合并后的场景包。

    `persona` 为根文件去掉 manifest 后的全部内容（含 `persona`/`target_user`/
    `emotion_calibration`/`memory`/`reminders`/`companion_ui` 等子键）。
    """

    manifest: dict
    persona: dict
    safety: Optional[dict] = None
    agents: dict = field(default_factory=dict)
    mobility: Optional[dict] = None
    physical_caps: Optional[dict] = None

    @staticmethod
    def _split_tools(declared: list, planned: list,
                     available: Optional[set]) -> tuple[list, list]:
        """把 agent 声明的工具切成（可暴露, 未注册仅诊断）两桶。

        `available` 为None 表示"未开启过滤"（老调用方/纯单测）：
        原样返回 declared。此时调用方须自行保证只暴露已注册工具。
        """
        declared = list(declared or [])
        planned = list(planned or [])
        if available is None:
            return _dedup(declared), _dedup(planned)
        exposed = [t for t in declared if t in available]
        # 未注册 = 路线图里planned_tools + 声明了但大脑没注册的 tools
        pending = planned + [t for t in declared if t not in available]
        return _dedup(exposed), _dedup(pending)

    def to_scene_payload(self, available_tools: Optional[Iterable[str]] = None) -> dict:
        """组装 MCP-CONTRACT §8 `self.suiyue.get_scene` 的返回体。

        `available_tools`：大脑 MCP **实际已注册**的工具名集合。
        传入后每个 agent 的工具会被过滤为两桶：
        - `tools`        —— 已注册，可安全暴露给 LLM；
        - `tools_pending` —— 路线图上但未注册（`planned_tools` 声明的，
          或 `tools` 里写了但大脑没注册的），**永不下发给 LLM**，仅供预检/排障。

        这是N1（"8 个工具未注册却被场景包声明"）的结构性修复：
        过滤发生在**大脑侧**——大脑最清楚自己注册了什么，
        消费方（xiaozhi overlay）无需重复实现过滤逻辑，也不会误暴露。
        """
        avail = set(available_tools) if available_tools is not None else None
        safety = self.safety or {}
        agents = []
        for name, agent in sorted(self.agents.items()):
            if not agent.get("enabled", True):
                continue
            exposed, pending = self._split_tools(
                agent.get("tools"), agent.get("planned_tools"), avail)
            agents.append(
                {
                    "name": name,
                    "system_prompt": agent.get("system_prompt"),
                    "tools": exposed,
                    "tools_pending": pending,
                    "trigger_examples": agent.get("trigger_examples", []),
                }
            )
        return {
            "scene_pack": self.manifest.get("scene_pack"),
            "device_model": self.manifest.get("device_model"),
            "persona": self.persona,
            "safety": {
                "hard_rules": safety.get("hard_rules", []),
                "disclaimer": safety.get("disclaimer"),
                "emergency": safety.get("emergency"),
            },
            "agents": agents,
            "emotion_calibration": self.persona.get("emotion_calibration"),
            "tool_visibility": {
                # false = 本次未传 available_tools，tools 未过滤（消费方自负风险）
                "filtered": avail is not None,
                "registered_count": len(avail) if avail is not None else None,
                "exposed_count": sum(len(a["tools"]) for a in agents),
                "pending_count": sum(len(a["tools_pending"]) for a in agents),
            },
        }


def _dedup(items: Iterable[str]) -> list:
    """去重且保序（工具清单要稳定，便于快照对比与测试断言）。"""
    seen: set = set()
    out: list = []
    for it in items or []:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


# --------------------------------------------------------------------------
# 基础 IO
# --------------------------------------------------------------------------
def discover_packs(packs_dir: str = PACKS_DIR) -> list[str]:
    """列出所有场景包 id（即子目录名，跳过以 _ 开头的临时目录）。"""
    if not os.path.isdir(packs_dir):
        return []
    return sorted(
        d
        for d in os.listdir(packs_dir)
        if os.path.isdir(os.path.join(packs_dir, d)) and not d.startswith("_")
    )


def _load_yaml(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_pack_raw(pack_id: str, packs_dir: str = PACKS_DIR) -> dict:
    """读单个包目录为原始结构（未展开继承）。"""
    pdir = os.path.join(packs_dir, pack_id)
    if not os.path.isdir(pdir):
        raise FileNotFoundError(f"场景包不存在: {pdir}")

    # 1) 根文件：persona.yaml 或 scene.yaml
    root: dict = {}
    for cand in _ROOT_CANDIDATES:
        rp = os.path.join(pdir, cand)
        if os.path.exists(rp):
            root = _load_yaml(rp)
            break

    # 2) manifest 抽取（从根文件顶层剥出）
    manifest = {k: root.pop(k) for k in MANIFEST_KEYS if k in root}
    persona = root  # 根文件去掉 manifest 后的全部内容

    # 3) agents/ 目录：每个文件一个 Agent
    agents: dict[str, dict] = {}
    adir = os.path.join(pdir, "agents")
    if os.path.isdir(adir):
        for fn in sorted(os.listdir(adir)):
            if not fn.endswith(".yaml"):
                continue
            ad = _load_yaml(os.path.join(adir, fn))
            name = ad.get("agent") or os.path.splitext(fn)[0]
            agents[name] = ad

    # 4) section 文件（safety/mobility/physical_caps）
    sections: dict[str, Optional[dict]] = {}
    for sec, fname in _SECTION_FILES.items():
        fp = os.path.join(pdir, fname)
        if os.path.exists(fp):
            d = _load_yaml(fp)
            sections[sec] = d.get(sec, d)  # 优先取顶层 sec 键，否则整文件即 section
        else:
            sections[sec] = None

    # 5) 兼容 PoC 包：若根文件内联了 section（kids_v1 的 safety），提升到对应 section
    for sec in _SECTION_FILES:
        if sections[sec] is None and sec in persona:
            sections[sec] = persona.pop(sec)

    return {
        "manifest": manifest,
        "persona": persona,
        "safety": sections["safety"],
        "agents": agents,
        "mobility": sections["mobility"],
        "physical_caps": sections["physical_caps"],
    }


# --------------------------------------------------------------------------
# 继承合并
# --------------------------------------------------------------------------
def _deep_merge(base: Any, override: Any) -> Any:
    """dict 递归深合并（子胜父）；list / 标量子包整体替换父包（ADR-012 D1）。"""
    if isinstance(override, dict) and isinstance(base, dict):
        out = dict(base)
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                out[k] = _deep_merge(base[k], v)
            else:
                out[k] = v  # 子包同键覆盖（含 list 替换）
        return out
    return override  # list / 标量：子包替换父包


def _merge_raws(parent: dict, child: dict) -> dict:
    """把 child 原始结构合并到已解析的 parent 上（子胜父）。"""
    out = {
        "manifest": child["manifest"],  # 子包自身 manifest（继承链上取末节）
        "persona": _deep_merge(parent["persona"], child["persona"]),
        "safety": _deep_merge(parent["safety"] or {}, child["safety"] or {}),
        "mobility": _deep_merge(parent["mobility"] or {}, child["mobility"] or {}),
        "physical_caps": _deep_merge(
            parent["physical_caps"] or {}, child["physical_caps"] or {}
        ),
        "agents": dict(parent["agents"]),  # 父 agents 先全量
    }
    # agents 目录并集：同名文件子包深合并覆盖，新名直接并入
    for name, ad in child["agents"].items():
        if name in out["agents"]:
            out["agents"][name] = _deep_merge(out["agents"][name], ad)
        else:
            out["agents"][name] = ad
    return out


def resolve_inheritance(
    pack_id: str, packs_dir: str = PACKS_DIR, _seen: Optional[list] = None
) -> dict:
    """展开 inherits 链（自底向上，子胜父），返回合并后的原始结构 dict。"""
    _seen = _seen or []
    if pack_id in _seen:
        raise ValueError(f"场景包继承环: {' -> '.join(_seen + [pack_id])}")
    raw = load_pack_raw(pack_id, packs_dir)
    parent = raw["manifest"].get("inherits")
    if parent:
        _seen.append(pack_id)
        pres = resolve_inheritance(parent, packs_dir, _seen)
        raw = _merge_raws(pres, raw)
    return raw


def load_resolved(pack_id: str, packs_dir: str = PACKS_DIR) -> ResolvedPack:
    """读包并展开继承，返回 ResolvedPack。"""
    raw = resolve_inheritance(pack_id, packs_dir)
    return ResolvedPack(
        manifest=raw["manifest"],
        persona=raw["persona"],
        safety=raw["safety"],
        agents=raw["agents"],
        mobility=raw["mobility"],
        physical_caps=raw["physical_caps"],
    )


def validate_pack(resolved: ResolvedPack) -> list[str]:
    """必填校验 + 引用完整性，返回 warning 列表（空=通过）。"""
    warns: list[str] = []
    if not resolved.manifest.get("scene_pack"):
        warns.append("manifest 缺 scene_pack")
    if not resolved.manifest.get("version"):
        warns.append("manifest 缺 version")
    if not resolved.manifest.get("device_model"):
        warns.append("manifest 缺 device_model（PoC 包可豁免）")
    if resolved.safety is None:
        warns.append("缺 safety.yaml（生产包必须有安全策略）")
    if not resolved.agents:
        warns.append("agents/ 为空（无可路由 Agent）")
    return warns


# --------------------------------------------------------------------------
# 版本比较（同 device_model 多包取最高 version）
# --------------------------------------------------------------------------
def _ver_tuple(v: str) -> tuple:
    parts: list = []
    for p in str(v).split("."):
        num = ""
        for ch in p:
            if ch.isdigit():
                num += ch
            else:
                break
        parts.append(int(num) if num else 0)
    return tuple(parts)


def select_by_model(model: str, packs_dir: str = PACKS_DIR) -> Optional[str]:
    """选 device_model == model 的包；同 model 多包取 version 最高。"""
    best: Optional[str] = None
    best_ver: tuple = (-1,)
    for pid in discover_packs(packs_dir):
        try:
            rp = load_resolved(pid, packs_dir)
        except Exception:
            continue  # 跳过损坏包，不阻断其他
        if rp.manifest.get("device_model") == model:
            ver = _ver_tuple(rp.manifest.get("version", "0"))
            if best is None or ver > best_ver:
                best, best_ver = pid, ver
    return best
