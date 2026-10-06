# e2e/ — 四方同台验收（CC BY-SA 4.0）

## 验收指标（第一学期 MVP / 四方同台）

| 指标 | 达标线 | 自动化覆盖 |
|---|---|---|
| 语音出声延迟 | ≤ 1.5s | `TestE2ELatency.test_speech_latency` |
| 动作起始延迟 | ≤ 2.5s | `TestE2ELatency.test_action_latency` |
| 三设备同步误差 | ≤ 300ms | `TestE2ELatency.test_sync_spread_across_bodies` |
| 连续运行 | 4h 无崩溃 | `TestE2EStability.test_repeated_dispatch`（CI 缩短为 50 轮） |
| 断网恢复 | 30s 内自恢复 | `TestE2EResilience`（模拟底盘掉线，验证优雅降级） |

> 这 5 项原来是纯文档口径，现已固化为可执行断言，改动即回归。

## 自动化运行（无需真机、无需云端）

```bash
# 装依赖
pip install -r suiyue/requirements-dev.txt

# 全量（单测 + e2e，55 个用例）
cd suiyue && python -m unittest discover -s . -p "test_*.py" -t .

# 只跑 e2e，日志更清晰
cd suiyue && python -m e2e.test_e2e -v
```

e2e 用 `daliang_gateway.mock_server` 在**随机高位端口**自起自收 mock 底盘，
CI 机器无需预置任何服务，也不会端口冲突。

## 覆盖的链路

```
LLM 意图 → SuiyueBrain.dispatch_emote → provider
        ├─ 大亮：ChassisGateway → WS → mock World（真实下发，断言位置变化）
        └─ 其余三体：StaticProvider 按能力注册表解析

MCP 工具：self.suiyue.{emote,list_devices,get_scene,poll_events}
         self.daliang.{navigate,patrol,approach,follow,get_status,stop_all,dock,region,add_marker}

场景包：pepper_cn_v1 继承 elder_cn_v1 → health + companion 双Agent
事件回路：底盘事件 → nudge（巡游到达/急停/低电量）
负路径：未知设备、未知工具、底盘掉线 —— 均须 isError 而非崩溃
```

## 10 句测试话术（`test_utterances.md`）

覆盖：寒暄、怀旧、健康、指令、情绪、重复叙事、口音鲁棒、防诈骗、求助、打断。

> 现状：话术表仍是**人工验收**清单（需真人说话、真机动作、真TTS）。
> `test_e2e.py` 覆盖的是它**下游**的意图分发与动作执行，不含 ASR/LLM/TTS 本身。
> 话术自动化需等云端对话引擎（`xiaozhi-esp32-server` fork）落地后再接。

## CI

`.github/workflows/ci.yml`：push/PR 触发，Python 3.11 + 3.13 双版本矩阵。

| 步骤 | 内容 |
|---|---|
| 编译检查 | 全部 `.py` 语法编译 |
| YAML 校验 | `tools/lint_yaml.py`（守护场景包格式事故） |
| 全部测试 | `unittest discover`（55 用例，含 e2e） |
| e2e 单独跑 | 独立步骤，失败日志更清晰 |
| Pepper 桥语法 | `naoqi_bridge` 在 Py3 下编译 + `SyntaxWarning` 视为错误 |

> Pepper 端侧 `naoqi_bridge` 是 Python 2.7 + Windows x86 + 真机 SDK，
> Linux CI 无法运行，故只做语法检查（不 import，不连 broker）。
