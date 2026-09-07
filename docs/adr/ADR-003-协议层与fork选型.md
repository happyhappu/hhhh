# ADR-003 协议层：小智协议 + MCP，fork 三个 MIT 上游

日期：2026-09-06（许可证核实 2026-09-07） ｜ 状态：已接受

## 决策
不造轮子：语音链路与云端编排以小智（xiaozhi）生态为基线，跨本体扩展用 MCP 工具表达。

## 三个 fork 上游（均 MIT，与 Apache-2.0 兼容）
| 层 | 上游 | 用途 |
|---|---|---|
| Otto 固件 | `78/xiaozhi-esp32`（14.8k star，70+ 硬件） | otto-robot 板级 + 语音链路 |
| Reachy 端侧 | `huangjunsen0406/py-xiaozhi`（© 2025 Junsen，MIT） | Python 客户端，支持树莓派 ARM + GPIO + MCP |
| 云端 | `xinnan-tech/xiaozhi-esp32-server`（MIT） | 网关/会话/插件体系 |

## 落选者
- **小歪 OpenDeskBot：GPL-3.0 传染**，与 Apache-2.0 冲突，且仅 2 舵机云台非双足——只读设计参考（用量看板、注视感知、免唤醒值得借鉴），**一行代码不搬**。

## Fork 纪律
upstream remote 常驻；自有改动隔离在 `suiyue/` overlay；改上游文件加 `[PATCH]` 前缀；`NOTICE` 维护归属。
