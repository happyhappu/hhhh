# brain/ — 云端大脑

fork 自 `xinnan-tech/xiaozhi-esp32-server`（MIT）。第一学期用小智模式直连跑通；第二学期按三层概念重写轻量实现（ADR-005）。

```
brain/
├── packs/                  # 场景包（ADR-007，热切换）
│   ├── elder_cn_v1/        # 老人场景（本学期主战场）
│   └── kids_v1/            # 小学生 PoC（插槽验证）
├── capabilities/            # 能力注册表：device_model → 能力与动作空间
│   ├── otto_v1.yaml
│   ├── reachy_mini_v1.yaml
│   └── daliang_v1.yaml
├── daliang_provider/        # 大亮本体云端编排层（意图→底盘命令 + 事件桥接）
│   ├── orchestrator.py      # DaliangOrchestrator（MCP-CONTRACT §1 的大亮实现）
│   └── test_chassis_orchestrator.py
├── core/                    # ★ 统一意图分发中枢（"一个大脑四个身体"云端侧）
│   ├── capability.py        # 加载 capabilities/<model>.yaml
│   ├── provider.py          # BodyProvider / StaticProvider（模拟固件）/ DaliangProvider（实时）
│   ├── brain.py             # SuiyueBrain：按 device_id 路由 emote 意图
│   ├── demo_four_bodies.py # 一句话四种反应演示（无需硬件）
│   └── test_brain.py
└── README.md
```

## core（统一分发中枢，新增）

把"一个大脑四个身体"在云端落地：收到一个 `self.suiyue.emote` 意图，`SuiyueBrain` 按各设备
的能力注册表翻译成不同具体反应；同一句话，otto / reachy / daliang 给出三种不同表达与动作。

- `StaticProvider`：仅按能力注册表解析意图（ottoreachy 未烧固件时演示/测试用，不真正执行）；
- `DaliangProvider`：包 `DaliangOrchestrator`，实时驱动大亮底盘；
- 本体无移动能力时，移动原语静默降级（`degraded=True`，MCP-CONTRACT §6）。

运行演示（无需硬件）：`python -m brain.core.demo_four_bodies`
运行测试：`python -m unittest brain.core.test_brain -v`

## daliang_provider（新增）

云端"大脑"对大亮本体的编排层，位于 chassis-gateway 与 Agent 之间：

- `DaliangOrchestrator.execute_intent({emotion, intensity, action_primitive, params})`：
  把 §1 情感意图翻译成 `self.daliang.*` 底盘命令；纯表情意图（无 `action_primitive`）委派给 companion-app，底盘不动作。
- `DaliangOrchestrator.handle_event(device_event)`：把底盘事件（patrol_arrive / emergency_stop / battery_low ...）翻译成对话上下文提示(nudge)，由 Agent 决定是否进记忆。
- `tool_schemas()` + `invoke_tool()`：作为 MCP provider 直接挂载到 xiaozhi-esp32-server fork。

依赖 `daliang/chassis-gateway` 的 `daliang_gateway` 包（已与真机协议同构，接真机仅改 url）。
运行测试：`python -m unittest brain.daliang_provider.test_chassis_orchestrator -v`

## 开发顺序（不等硬件）

1. `capabilities/*.yaml` 能力注册表——契约的机器可读版；
2. `packs/elder_cn_v1/` 场景包内容——persona / agents / safety；
3. 与 `daliang/chassis-gateway` 的 Mock Server 联调 `self.daliang.*` 工具。

## 接入约定

- 对话下行意图格式见 `../docs/MCP-CONTRACT.md`；
- 原上游代码改动遵守 fork 纪律（`suiyue/` overlay + `[PATCH]` 前缀）。
