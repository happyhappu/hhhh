# Pepper `naoqi_bridge`（Python 2.7 桥）

Pepper 端侧最末端的协议桥：连 Pepper broker（`tcp://<ip>:9559`），把云端（Python 3 `suiyue-pepper` 主网关）下发的动作原语派发到 NAOqi proxy，并把麦克风音频帧 / 在场感知事件回传云端（音频 → 云 FunASR 流式识别；事件 → 云端主动交互）。

> **为什么要这一层？** 官方 `pynaoqi` SDK（2.5.7.1 构建）**仅支持 Python 2.7**，而 Pepper 固件是 NAOqi 2.5.10.7。大脑主逻辑在 Py3.13，故在网关机（**必须 Windows x86 主机**，见下）起一个轻量 **Py2.7 子进程**跑本桥，经本地 TCP 与 Py3 主网关 IPC 通信。Pepper 本体仍作纯瘦客户端（无本地 LLM/ASR/TTS）。

## ⚠️ 运行平台硬约束（重要）

手上的 pynaoqi SDK 是 **`win32-vs2013` 构建（32 位）**。因此：

- **网关机必须是 Windows x86 主机**（64 位 Windows 也可，但必须装 **32 位 Python 2.7**）。
- **不能用树莓派 / ARM / Linux** 跑本桥（其 `.pyd` 无法加载）。
- 主网关 `suiyue-pepper` 是 Py3.13，可跑在任意平台；它与本桥经本地 TCP 通信，跨机器也行（同 VLAN 内）。

## 目录（v0.2 完整实现）

```
naoqi_bridge/
├── bridge.py        # 主入口：连 broker + 本地 IPC 派发 + 失联看门狗 + 优雅关闭
├── config.py        # 全局常量（连接/音频/限速/看门狗）
├── proxies.py       # PepperProxies：惰性探测并缓存所有 NAOqi proxy（含降级）
├── motion.py        # 运动/表情/急停/姿态/状态（ALMotion/ALRobotPosture/ALAnimationPlayer）
├── navigation.py    # 导航/巡游（ALMotion.moveTo；ALNavigation 可选增强）
├── tablet.py        # 平板渲染（ALTabletService.showWebview）
├── vision.py        # 在场感知（订阅 ALFaceDetection / ALPeoplePerception 事件）
├── audio.py         # 麦克风捕获（经典 ALBroker + ALModule 接收 processRemote 回调）
├── requirements.txt # 依赖说明（纯标准库 + pynaoqi SDK，无 pip 包）
└── README.md
```

> 配套 Py3 联调客户端：`../test_bridge_client.py`（不依赖 Py2 SDK，用于无 Pepper 时验证 IPC 协议与音频帧格式）。

## 运行环境

SDK 路径：`../../pynaoqi-python2.7-2.5.7.1-win32-vs2013/`（工作区根，**未纳入 git**）。

```bat
:: Windows 启动示例（Py2.7 x86 解释器）
set SDK=D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013
set PYTHONPATH=%SDK%\lib
set PATH=%SDK%\bin;%SDK%\lib;%PATH%

python2.7 bridge.py --qi-url tcp://192.168.31.<pepper-ip>:9559
```

连接用 `qi.Session().connect(...)`（命令/状态查询）；音频回调用经典 `naoqi.ALBroker` + `naoqi.ALModule`（NAOqi 仅对注册模块回调 `processRemote`）。两套均随 SDK 提供。

## 本地 IPC 协议（主网关 ↔ 桥，JSON 行）

主网关作为 TCP 客户端连 `127.0.0.1:9560`，按 **JSON 行**（`\n` 分隔）通信：

- 下行（主网关 → 桥）：`{"id":1,"action":"approach","params":{"distance":0.3}}`
  - `action` ∈
    `ping`(心跳) /
    `emote`{animation} /
    `approach`{distance} /
    `navigate`{goal|[x,y,theta] 或 node} /
    `patrol`{points,loops,speed} /
    `tablet_render`{url} / `tablet_clear`{} /
    `posture`{name} / `head_nod`{} / `head_shake`{} /
    `audio_start`{} / `audio_stop`{} /
    `vision_start`{} / `vision_stop`{} /
    `stop_all`{} / `get_status`{}
- 上行（桥 → 主网关）：
  - 响应：`{"id":1,"ok":true,"result":{...}}` 或 `{"id":1,"error":"..."}`
  - 音频帧：`{"type":"audio","rate":16000,"channels":1,"data_b64":"..."}`（base64 内联，性能优化见下）
  - 感知事件：`{"type":"event","name":"FaceDetected","data":[...]}`
  - 心跳回包：`{"id":1,"ok":true,"result":{"pong":true}}`

> 音频上行用 base64 是为规避 TCP 行协议中的 `\n` 冲突，简单稳妥；真机验证后若带宽吃紧，可改裸字节流子协议（长度前缀帧）。

## 动作原语 ↔ NAOqi proxy（对齐 `pepper_v1.yaml`）

| action | 控制器 / proxy | 说明 |
|---|---|---|
| `emote` | `motion.py` / ALAnimationPlayer | 挥手/拥抱等；未知标签回退到关节级点头 |
| `approach` | ALMotion.moveTo + ALBasicAwareness(可选) | 面向并前移半步（限速内） |
| `navigate` | ALMotion.moveTo（ALNavigation 可选） | [x,y,theta] 或拓扑节点名 |
| `patrol` | ALMotion.moveTo ×N | 巡游航点序列 |
| `tablet_render` | ALTabletService.showWebview | 平板问候语/字幕/表情（URL 由主网关托管） |
| `posture` | ALRobotPosture.goToPosture | Stand/Sit/Crouch |
| `head_nod` / `head_shake` | ALMotion 角度插值 | 点头/摇头（较稳，不依赖动画标签） |
| `stop_all` | ALMotion.killAllTasks + rest | 急停 + 去刚度；同步退订音频/视觉 |
| `get_status` | ALRobotPosture/ALMemory | 姿态/电量/连接 |
| `audio_start/stop` | `audio.py` / ALAudioDevice | 麦克风订阅（前麦 16k 单声道） |
| `vision_start/stop` | `vision.py` / ALMemory 事件 | 人脸/人体感知上抛 |

## 安全与降级

- **限速**：所有 `moveTo` 夹紧在 `MAX_MOVE_SPEED=0.4 m/s`（三轮底盘物理上限）。
- **失联看门狗**：主网关 > `WATCHDOG_TIMEOUT_S=15s` 无心跳 → 自动 `stop_all`（ADR-011 §决策3）。
- **Proxy 降级**：`proxies.py` 探测时若某 proxy `service not found`（如 ALNavigation/ALTracker），记 None 并优雅降级，不阻塞主流程。
- **急停链路**：`stop_all` 先退订音频/视觉，再 `killAllTasks` + `rest()`（去刚度）；机身倾斜由 NAOqi 硬件跌倒保护兜底。
- **禁用云端服务**：Pepper 内置 ALSpeechRecognition/ALTextToSpeech/ALDialog/ALAutonomousLife 不实例化（对话/意图/音色全走云端），见 `pepper_v1.yaml` `disabled_cloud_services`。

## 当前状态与 TODO（真机验证前）

- [x] SDK 已获取（pynaoqi 2.5.7.1，Py2.7，VC120），`import qi` / `import naoqi` 双 API 可用
- [x] 完整动作原语 / 音频 / 感知 / 平板 / 急停 / 状态上报实现（纯标准库）
- [x] 失联看门狗 + 优雅关闭（SIGINT/SIGTERM）
- [x] Py3 联调客户端 `../test_bridge_client.py`（无 Pepper 也能验证 IPC 协议）
- [ ] **真机联调**：`qi.Session().connect` 在 NAOqi 2.5.10.7 实际连通性
- [ ] `audio.py` 回调 `processRemote` 在 2.5.10.7 实测（通道顺序 `FRONT_MIC_CHANNEL`、buffer 布局）
- [ ] `emote` 动画标签 / `approach` 前移距离按真机礼仪调参
- [ ] 音频帧 base64 上行性能优化（真机改用裸字节流）
- [ ] 与 `suiyue-pepper` 主网关（Py3）端到端联调（主网关代码见 `suiyue/pepper/` 规划）

> ⚠️ 本桥代码按 NAOqi 2.5 培训文档接口形状编写，**未经 NAOqi 2.5.10.7 真机验证**；真机若 proxy/方法名/事件名有出入，按模块局部调整即可（已用 `⚠️` 标注所有待确认点）。
