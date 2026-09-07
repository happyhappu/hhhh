# 岁悦系统架构（v1）

> 对应决策：ADR-002（三本体一脑）、ADR-003（小智协议+MCP）、ADR-004（情感意图抽象）、ADR-009（大亮双网关）。

## 1. 总览

```
                    ┌────────────────────────────────────────────┐
                    │           云端大脑  brain/                  │
                    │  xiaozhi-esp32-server（MIT fork）+ 岁悦扩展 │
                    │                                            │
                    │  接入网关(WS) → 会话编排(Intent Router)     │
                    │      ├─ LLM 路由：8B 快模型 / 30B+ 高价值    │
                    │      ├─ 记忆三层：Redis 短期 / 向量库长期   │
                    │      │   / MySQL 结构化画像                 │
                    │      └─ 场景包 packs/elder_cn_v1 ...        │
                    │  能力注册表 capabilities/（device → 能力） │
                    └───────────────┬────────────────────────────┘
                                    │ 小智协议 + MCP
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
┌───────▼────────┐         ┌────────▼────────┐         ┌───────▼────────┐
│ Otto            │         │ Reachy Mini     │         │ 大亮           │
│ firmware-esp32/ │         │ client-py/      │         │ chassis-gateway│
│                │         │                 │         │ + companion-app│
│ ESP32-S3 固件   │         │ 树莓派5 Python  │         │ 见 §4 拆分     │
│ {emotion,int.} │         │ {emotion,int.}  │         │ {emotion,int., │
│ → 双足动作      │         │ → 头/天线/LED   │         │  primitive,params}│
└────────────────┘         └─────────────────┘         └────────────────┘
```

**核心不变量：云端不知道每台机器人长什么样。** 云端只表达"我想要什么"（情感意图 +
可选动作原语），端侧按自己的能力注册表把它翻译成实际动作。换本体、加本体，不改云端。

## 2. 一次对话的完整数据流

```
老人开口（免唤醒，VAD 人声门控 + 视觉在场门控）
 → 端侧拾音，Opus 编码，WS 上行
 → 云端 ASR（Paraformer）→ 文本
 → Intent Router：闲聊走 8B，健康/情感/安全走 30B+
 → 上下文组装：Redis 短期(10轮) + 向量库召回(top-5) + MySQL 画像标签
 → LLM 生成：{reply 文本, emotion, intensity, [action_primitive]}
 → TTS 流式下行 + 意图并行下行
 → 端侧：扬声器播报 ∥ 编排器查能力注册表 → 本体动作
 → 记忆抽取：值得记住的事实 embedding 入库（相似度>0.92 只累加计数）
```

## 3. 模块职责边界

| 模块 | 只负责 | 绝不负责 |
|---|---|---|
| `brain/` | 对话编排、记忆、画像、场景策略、能力注册 | 音频编解码、任何硬件细节 |
| `firmware-esp32/` | Otto 音频链路 + 情感→动作映射（`suiyue/` overlay） | 联网业务逻辑、记忆 |
| `client-py/` | Reachy 端侧全栈（音频/UI/动作 MCP 工具） | 对话决策 |
| `daliang/chassis-gateway/` | 底盘协议 ↔ MCP 工具的翻译层 + Mock Server | 语音/屏幕/表情（那是 companion-app 的事） |
| `daliang/companion-app/` | 大亮表现层（听/说/看/表情），`VendorSdkBridge` 为唯一厂商依赖点 | 底盘运动（经 chassis-gateway） |

## 4. 大亮的特殊架构（双网关拆分）

大亮 = 易行 EGO AGV 底盘（L4 明文 JSON 网络协议）+ 整机厂 Android 上位机。因此拆两个独立件：

- **`chassis-gateway`**：跑在**任何与底盘同局域网的设备**上（实验室服务器/树莓派均可，不必在大亮上）。连 `ws://192.168.31.7:6060` / MQTT `:1883`。接口已齐，**现在就能基于 Mock Server 开发**。
- **`companion-app`**：必须跑在大亮 Android 上位机。接口待尽调函回复；若拿不到走 Plan B（外挂 SBC 交互头，见 ADR-009）。

依赖纪律：`companion-app` 里 **`bridge/VendorSdkBridge.kt` 是唯一允许 import 厂商 SDK 的文件**，其余代码只面向自有接口 `SuiyueSurface`。

## 5. 部署形态（两套，接口隔离）

| 形态 | 场景 | 算力 |
|---|---|---|
| 实验室边缘 | 本期教学/科研，8–10 路并发 | 现有 4090（吞吐优先）；DGX Spark 仅作大模型/微调节点 |
| 产品化（远期） | 养老驿站/家庭 | 云端 API 或家用小盒子 |

机器人端只认一个 API 契约（`docs/MCP-CONTRACT.md`），不关心背后是 4090 还是云。

## 6. 隐私与安全底线（酌情保障档）

- 图像仅内存处理、不落盘；摄像头物理遮挡开关；
- 机器人必须在**无摄像头**模式下跑通完整陪伴链路（视觉是可选增强）；
- 大亮 geofence：`region` 虚拟墙做卧室/卫生间禁入；
- 底盘软急停 `softScram` 挂到云端 `stop_all` 工具，任何 Agent 可调用。
