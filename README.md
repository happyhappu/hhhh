# 岁悦 SuiYue — 多形态陪伴机器人开源项目

> 一个软件大脑，三个机器人身体：Otto（桌面双足）、Reachy Mini（桌面表达）、大亮（1.56m 移动人形）。
> 教学载体优先，产品化为远期愿景。首轮场景：居家老人陪伴。

## 仓库地图

| 模块 | 路径 | 职责 | 上游（fork 自） | 许可证 | 状态 |
|---|---|---|---|---|---|
| 云端大脑 | `brain/` | WS 接入、会话编排、LLM 路由、记忆三层、能力注册表、场景包 | `xinnan-tech/xiaozhi-esp32-server`（MIT） | Apache-2.0 | 骨架已建 |
| Otto 固件 | `firmware-esp32/` | 小智 otto-robot 板级 + 岁悦情感映射层 | `78/xiaozhi-esp32`（MIT） | Apache-2.0 | 待 fork |
| Reachy 端侧 | `client-py/` | Python 端侧客户端（跑在树莓派 5 / Linux SBC） | `huangjunsen0406/py-xiaozhi`（MIT） | Apache-2.0 | 待 fork |
| 大亮底盘网关 | `daliang/chassis-gateway/` | EGO 底盘 WS/MQTT 协议 → MCP 工具，含 Mock Server | 自研 | Apache-2.0 | 骨架已建 |
| 大亮上位机 App | `daliang/companion-app/` | Android 原生 Kotlin 表现层 APK | 参考 `xuan2261/xiaozhi-ai-android` | Apache-2.0 | 待尽调后启动 |
| 硬件 | `hardware/` | Otto BOM、Reachy 加屏结构件、外挂交互头（Plan B） | Otto DIY（CERN-OHL-S 兼容） | CERN-OHL-S | 文档 |
| 课程包 | `course/` | 12+2 讲课程、实验手册、验收标准 | 自研 | CC BY-SA | 大纲已建 |
| 端到端验收 | `e2e/` | 10 句测试话术、延迟与稳定性指标 | 自研 | CC BY-SA | 骨架已建 |

设计决策完整版见 `docs/adr/`（ADR-001 ~ 011）与上级目录的四份设计文档。

**部署基线（必读）**：全系统默认 **全离线（air-gapped）** —— 小智云端 + 本地大模型 + chassis-gateway 全部跑在自有 4090 单卡上，不依赖任何公网 API。24GB 显存预算、LLM 路由档位与七项隐形联网点见 `docs/adr/ADR-011-全离线部署基线.md`；部署与验收走 `docs/OFFLINE-CHECKLIST.md`。

## 分层架构（一句话版）

```
云端大脑 brain/（小智协议 + MCP）
   ├─ Otto      firmware-esp32/   情感→双足动作（<200 行 C++ 映射层）
   ├─ Reachy    client-py/         情感→头颈/天线/LED（Python MCP 工具）
   └─ 大亮      chassis-gateway/   情感+移动→导航/巡航（纯网络协议）
                companion-app/     听/说/看/表情（Android，Plan B 可外挂替代）
```

详见 `docs/ARCHITECTURE.md`；跨本体工具契约见 `docs/MCP-CONTRACT.md`。

## 快速开始（分阶段）

**阶段 0（教师预研，现在）**
1. 按上级目录《岁悦-阶段0-采购清单与教师预研checklist-v1.md》采购；
2. `daliang/chassis-gateway/` 不需要真机——先跑 Mock Server 开发全部底盘侧软件；
3. 发出《上位机接口尽调函》，等待厂家书面回复后决定 companion-app 走 B1/B1+B3/纯 B3。

**阶段 1（第 1–4 讲）**：fork 三个上游仓库（各目录 `FORK.md` 有具体命令与改造点），跑通"能听能说能动"，改人设。

**阶段 2（第 5–8 讲）**：自建轻量云端 + 动作语义层落地——同一句话在三台机器人上给出不同动作回应。

## Fork 纪律（写给每一届学生）

1. fork 后保留 `upstream` remote，每学期同步一次上游；
2. 自有改动一律隔离在 `suiyue/` 目录内，禁止散改上游文件；
3. 必须改上游文件时，commit message 加 `[PATCH]` 前缀，方便 rebase 时识别；
4. 上游是 MIT，我们是 Apache-2.0：`NOTICE` 文件维护归属，不许删。

## 许可证

- 代码：Apache-2.0（`LICENSE`）
- 硬件：CERN-OHL-S 2.0（`hardware/`）
- 课程与文档：CC BY-SA 4.0（`course/`、`docs/`、`e2e/`）
