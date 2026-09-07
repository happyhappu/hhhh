# daliang/chassis-gateway/ — 大亮底盘网关

**性质**：自研（Apache-2.0）｜ **状态**：可立即开发（不等真机、不等尽调函）｜ **语言**：Python

## 是什么

把易行 EGO 底盘的明文 JSON 协议（`ws://192.168.31.7:6060` / MQTT `:1883`）翻译成
MCP 工具（`self.daliang.*`，契约见 `../../docs/MCP-CONTRACT.md`），注册到小智云端。
**跑在任何与底盘同局域网的设备上，不必在大亮上。**

```
chassis-gateway/
├── gateway/
│   ├── protocol.py        # 底盘命令封装（navigation/multiPointCruise/eventNavigation/softScram/charge/region...）
│   ├── mcp_tools.py       # MCP 工具注册与参数校验
│   └── events.py          # 到达回调(1000/1001)、急停、低电量 → 云端事件上行
├── mock/
│   └── mock_server.py     # ★ 先写这个：模拟底盘 WS 服务器，应答全部核心命令
└── README.md
```

## 开发顺序

1. **Mock Server**（1 人 3–5 天）：实现 `ws://localhost:6060`，应答
   `getAgvStatus` / `navigation` / `multiPointCruise`（含到达回调时序）/
   `eventNavigation`+`incidentRelease` / `softScram` / `charge` / `region`；
2. `protocol.py` + `mcp_tools.py` 基于 Mock 联调；
3. 阶段 B 编排逻辑（巡游 + 走到身边停下说话）全部在 Mock 上演通；
4. 真机到货：IP 从 `localhost` 换成 `192.168.31.7`，仅此而已。

## 依据文档

- 上级目录：`大亮TCP协议.txt`（63 页全文提取）、`岁悦-大亮SDK开放层级评估报告-v1.md`
- 错误码 10000–60000 全表在 TCP 协议文档内，`protocol.py` 需要完整映射。
