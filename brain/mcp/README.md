# 岁悦大脑 · MCP Server

把云端统一意图分发中枢 `SuiyueBrain` 暴露成一个**标准 MCP server**，让 `xiaozhi-esp32-server`（小智云端）以标准工具调用驱动"一个大脑三个身体"。

> 这是 ADR-002「三本体一脑」+ MCP-CONTRACT 的云端收敛点：云端只下发 `self.suiyue.emote`，端侧按各自能力注册表决定具体动作；大亮底盘的 `self.daliang.*` 工具也一并暴露给 Agent 做看护编排。

## 1. 暴露的工具

| 工具 | 说明 |
|---|---|
| `self.suiyue.emote` | 情感意图（**核心**）。参数 `emotion`/`intensity`/可选 `action_primitive`/`params`/`device_id`。`device_id` 省略或 `all` 时广播给所有本体；同一句话，otto / reachy / daliang 各自给出合理反应。 |
| `self.suiyue.list_devices` | 列出已注册本体 device_id（运维/排障）。 |
| `self.suiyue.poll_events` | 拉取底盘事件翻译出的对话上下文提示(nudge)，如巡游到达、软急停、低电量。 |
| `self.daliang.*`（9 个） | 大亮底盘工具：`navigate`/`patrol`/`approach`/`follow`/`get_status`/`stop_all`/`dock`/`region`/`add_marker`（契约见 `docs/MCP-CONTRACT.md` §2）。 |

所有工具名称、input schema 与 [MCP-CONTRACT.md](../../docs/MCP-CONTRACT.md) 严格一致。

## 2. 运行

```bash
# 在 suiyue/ 根目录，venv 激活
python -m brain.mcp --config brain/mcp/config.yaml
```

`--log <path>` 可把运行日志写到文件（stdout 只走 JSON-RPC，日志一律 stderr/文件）。

### 本地联调（无需真机）

1. 起一个底盘模拟器（与真机协议同构）：
   ```python
   # 任意脚本里
   import asyncio, websockets
   from daliang_gateway.mock_server import make_handler
   from daliang_gateway.world import World
   async def main():
       w = World()
       await websockets.serve(make_handler(w), "127.0.0.1", 6060)
       await asyncio.Future()
   asyncio.run(main())
   ```
2. 把 `config.yaml` 里 `daliang.chassis.url` 改为 `ws://127.0.0.1:6060`，再启动 MCP server。

## 3. 接入 xiaozhi-esp32-server（fork）

xiaozhi-esp32-server 支持把外部进程作为 **stdio MCP server** 接入（其 MCP client 会 spawn 子进程、读 stdout 的 JSON-RPC）。只需在它的 MCP 配置里登记本 server：

```yaml
# xiaozhi-server 的 mcp 配置（示意字段名以该仓库实际为准）
mcpServers:
  suiyue-brain:
    command: python
    args:
      - "-m"
      - "brain.mcp"
      - "--config"
      - "/abs/path/to/suiyue/brain/mcp/config.yaml"
    env:
      PYTHONPATH: "/abs/path/to/suiyue"   # 保证能 import brain.* 与 daliang_gateway
```

接入后，小智云端 LLM 直接能调用 `self.suiyue.emote` 等工具；调用 `self.suiyue.poll_events` 可把大亮看护事件拉回对话上下文。

> 若所用 xiaozhi-server 版本尚未支持 MCP client，可退化为「函数工具」：把 `SuiyueMCPServer.call_tool(name, args)` 包一层注册成小智的 FunctionCall handler 即可（核心方法 `list_tools()` / `call_tool()` 完全传输无关，复用即可）。

## 4. 设计要点

- **传输无关**：`SuiyueMCPServer` 只产出工具清单与调用结果，`__main__.py` 负责 stdio JSON-RPC。要换 SSE/HTTP 传输只需替换入口，不动大脑逻辑。
- **容错**：大亮底盘离线时 server 照常启动，`self.daliang.*` 调用返回 `isError` 而非崩溃；otto/reachy 走 `StaticProvider`，不依赖硬件。
- **事件回流**：底盘事件经 `DaliangOrchestrator.handle_event` 翻译成 nudge，存内存环形日志，`poll_events` 拉取。
- **零改动契约**：工具名/schema 与 MCP-CONTRACT 绑定，改契约须走 ADR。
