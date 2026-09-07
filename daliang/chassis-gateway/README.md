# daliang/chassis-gateway/ — 大亮底盘网关

**性质**：自研（Apache-2.0）｜ **状态**：✅ 已实现（底盘模拟器 + 网关 + 测试通过）｜ **语言**：Python（asyncio + websockets）

把易行 EGO 底盘的明文 JSON 协议（`ws://192.168.31.7:6060` / MQTT `:1883`）翻译成
MCP 工具（`self.daliang.*`，契约见 `../../docs/MCP-CONTRACT.md`），注册到小智云端。
**跑在任何与底盘同局域网的设备上，不必在大亮上。**

```
chassis-gateway/
├── requirements.txt           # websockets>=12.0
├── daliang_gateway/           # 包
│   ├── protocol.py            # 协议常量 + 响应构造（依据大亮TCP协议.txt）
│   ├── world.py               # 底盘模拟器的 2D 世界模型（运动学 + 事件调度）
│   ├── mock_server.py         # ★ 底盘模拟器（WS 服务器，无需真机）
│   ├── client.py              # 连底盘(或模拟器)的异步客户端（seq 关联 + 事件上行）
│   ├── events.py              # 事件 -> MCP-CONTRACT device_event 格式化
│   ├── mcp_tools.py           # self.daliang.* 工具清单 + 分发
│   └── gateway.py             # ChassisGateway：工具 <-> 底盘命令 翻译 + 事件上行
├── demo_client.py             # 演示脚本（自带模拟器，一键跑全流程）
├── test_protocol.py           # 单元测试（无真机、无网络）
└── README.md
```

## 已实现命令（与协议文档一致）

| 命令 | 模拟器行为 | 对应 MCP 工具 |
|---|---|---|
| `getAgvStatus` | 返回完整状态快照（位姿/电量/急停/置信度…） | `self.daliang.get_status` |
| `navigation` | 自由导航到坐标，到达发 `goal_reached` | `self.daliang.navigate` |
| `navigationById` | 按标记点 id 导航 | （navigate 的内部路径） |
| `multiPointCruise` | 循环巡游，每点上报 `1001`出发/`1000`到达/完成后`0` | `self.daliang.patrol` |
| `eventNavigation`+`incidentRelease` | 走到点暂停，等 `release` 释放 | `self.daliang.approach` |
| `remoteControl` | 速度环（x 前 m/s，t 转 rad/s） | `self.daliang.follow` |
| `softScram` | 软急停锁轮，发 `emergency_stop` | `self.daliang.stop_all` |
| `charge` | 回桩/取消 | `self.daliang.dock` |
| `region` | 虚拟墙/减速区（geofence） | `self.daliang.region` |
| `clearTask` / `setNavCollisionMode` | 清任务 / 防撞模式 | — |
| `getLaser` / `getCamera` | 30m 激光 + 深度点云（**非 RGB 图像**） | 阶段 B `vision_observe` |
| `marker` | 标记点增删查清 | （navigate_by_id 依赖） |

> 注意：`getCamera` 返回的是**深度点云**（文档同构），不是 RGB 图像帧——
> 与 SDK 评估报告一致：表现层（看老人）走 companion-app，底盘只给避障深度。

## 快速开始

```bash
cd suiyue/daliang/chassis-gateway
python -m venv .venv && .venv/Scripts/activate      # Windows
pip install -r requirements.txt

# 1) 跑演示（会自动起一个 ws://localhost:6060 模拟器）
python demo_client.py

# 2) 跑单元测试
python -m unittest test_protocol -v
```

## 单独启动模拟器（给其他组件联调）

```bash
python -m daliang_gateway.mock_server        # 监听 0.0.0.0:6060
```

此时 `firmware-esp32` / `client-py` 的编排层、或 `brain` 的接入网关，都可在
`ws://localhost:6060` 上联调，无需真机。

## 接真机：只改一个地址

```python
from daliang_gateway import DaliangChassisClient, ChassisGateway
# localhost -> 真机固定内网地址
client = DaliangChassisClient("ws://192.168.31.7:6060")
gw = ChassisGateway(client, upstream_event=my_upstream)
await gw.start()
```

协议是明文 JSON，与真实底盘完全同构（命令名、响应信封、1000/1001 回调码一致），
模拟器里验证过的逻辑直接对真机生效。

## 注册到小智云端 MCP

`mcp_tools.TOOLS` 是标准工具清单，`mcp_handle(gateway, tool, params)` 是分发函数。
把 `ChassisGateway` 包进 `xiaozhi-esp32-server`（MIT fork）的 MCP provider，
即可让云端编排器以 `self.daliang.*` 调用底盘——这正是 ADR-009「双网关拆分」的落地。

## 依据文档

- 上级目录：`大亮TCP协议.txt`（63 页全文提取）、`大亮HTTP协议.pdf`
- `../../docs/MCP-CONTRACT.md`（§2 底盘工具、§3 事件上行）
- `../../docs/adr/ADR-009-大亮双网关与PlanB.md`
