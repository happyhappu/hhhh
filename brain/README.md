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
└── README.md
```

## 开发顺序（不等硬件）

1. `capabilities/*.yaml` 能力注册表——契约的机器可读版；
2. `packs/elder_cn_v1/` 场景包内容——persona / agents / safety；
3. 与 `daliang/chassis-gateway` 的 Mock Server 联调 `self.daliang.*` 工具。

## 接入约定

- 对话下行意图格式见 `../docs/MCP-CONTRACT.md`；
- 原上游代码改动遵守 fork 纪律（`suiyue/` overlay + `[PATCH]` 前缀）。
