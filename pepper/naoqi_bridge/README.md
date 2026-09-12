# Pepper `naoqi_bridge`（Python 2.7 桥）

Pepper 端侧最末端的协议桥：连 Pepper broker（`tcp://<ip>:9559`），把云端（Python 3 `suiyue-pepper` 主网关）下发的动作原语派发到 NAOqi proxy，并把麦克风音频帧回传云端（→ 云 FunASR 流式识别）。

> **为什么要这一层？** 官方 `pynaoqi` SDK（2.5.7.1 构建）**仅支持 Python 2.7**，而 Pepper 固件是 NAOqi 2.9。大脑主逻辑在 Py3.13，故在实验室服务器起一个轻量 **Py2.7 子进程**跑本桥，经本地 TCP 与 Py3 主网关 IPC 通信。Pepper 本体仍作纯瘦客户端（无本地 LLM/ASR/TTS）。

## 目录
```
naoqi_bridge/
├── bridge.py     # 主入口：连 broker + 本地 IPC 派发 + 急停
├── audio.py      # 麦克风捕获（ALAudioDevice/ALMemory 事件，参照培训文档 2-3 节）
└── README.md
```

## 运行环境（关键）
SDK 路径：`../../pynaoqi-python2.7-2.5.7.1-win32-vs2013/`（工作区根，**未纳入 git**）。

**必须用 Python 2.7** 解释器运行本目录。干净 Windows 即可，无需另装 VS2013 运行库（`bin/msvcr120.dll`、`bin/msvcp120.dll` 已随包）。

```bat
:: Windows 启动示例
set SDK=D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013
set PYTHONPATH=%SDK%\lib
set PATH=%SDK%\bin;%SDK%\lib;%PATH%

python2.7 bridge.py --qi-url tcp://192.168.31.<pepper-ip>:9559
```

连接用 `qi.Session().connect(...)`（或 `from naoqi import ALProxy`）；两套 API 都在 SDK 包内。

## 本地 IPC 协议（主网关 ↔ 桥）
主网关作为 TCP 客户端连 `127.0.0.1:9560`，按 **JSON 行** 通信：
- 下行（主网关 → 桥）：`{"id":1,"action":"approach","params":{}}`
  - `action` ∈ `emote / approach / navigate / patrol / tablet_render / stop_all / get_status / audio_start / audio_stop`
- 上行（桥 → 主网关）：
  - 响应：`{"id":1,"ok":true,"result":{...}}` 或 `{"id":1,"error":"..."}`
  - 音频帧：`{"type":"audio","rate":16000,"channels":1,"data_b64":"..."}`（base64 仅骨架用，性能优化见下）

## 动作原语（对齐 `pepper_v1.yaml`）
| action | NAOqi proxy | 说明 |
|---|---|---|
| `emote` | ALAnimationPlayer | 挥手/拥抱等预制动画 |
| `approach` | ALMotion.moveTo + ALTracker | 靠近对话对象 |
| `navigate` | ALMotion.moveTo（ALNavigation 可选降级） | 目标点移动 |
| `patrol` | ALMotion.moveTo ×N | 巡游航点 |
| `tablet_render` | ALTabletService.showWebview | 平板问候语/字幕/表情 |
| `stop_all` | ALMotion.killAllTasks | 急停（失联看门狗触发） |
| `get_status` | ALRobotPosture/ALMemory | 姿态/连接状态上报 |

## 当前状态与 TODO（真机验证前）
- [x] SDK 已获取（pynaoqi 2.5.7.1，Py2.7，VC120），`import qi` / `import naoqi` 双 API 可用
- [x] 架构与 IPC 协议骨架就位
- [ ] **真机联调**：`qi.Session().connect` 在 NAOqi 2.9 实际连通性（文档实证 `--qi-url` 直连无需白名单）
- [ ] `audio.py` 回调签名/事件名在 2.9 上实测（ALAudioDevice/`ALAudioDevice/<name>` 事件）
- [ ] 音频帧 base64 上行性能优化（真机改用裸字节流/共享内存）
- [ ] 失联看门狗：主网关断连 > N 秒 → 自动 `stop_all`（跨进程心跳）
- [ ] `emote` 动画标签与 `approach` 前移距离按真机礼仪调参

> ⚠️ 本桥代码按 NAOqi 2.5 培训文档接口形状编写，**未经真机验证**；真机 2.9 上若某 proxy `service not found`，按 `pepper_v1.yaml` 降级（ALNavigation 等可选模块先不依赖）。
