# Pepper 真机联调 Checklist（NAOqi 2.9 + pynaoqi 2.5.7.1 桥）

> **背景**：Pepper 固件 NAOqi 2.9，端侧用 `pynaoqi-python2.7-2.5.7.1-win32-vs2013`（Py2.7-only）起 `qi-bridge` 子进程连 broker，Py3 主网关经本地 TCP:9560 IPC 派发动作原语、回收麦克风音频。已确认 **Pepper 开机免联网激活**，故 100% 内网可长期运行。
>
> **本文档用途**：在「一台装 Py2.7 的联调机 + 通电同网的 Pepper」就位后，照此逐项验证 `naoqi_bridge/` 的可运行性。所有带 ⚠️ 的项为代码按 NAOqi 2.5 文档形状编写、**未经真机验证**，需真机实测确认，是本次联调的核心目标。
>
> **关联文件**：`pepper/naoqi_bridge/{bridge.py,audio.py,README.md}`、`brain/capabilities/pepper_v1.yaml`。

---

## §0 硬件与网络前置

- [ ] Pepper 上电、立于平整无障碍区，物理急停按钮（后颈/底座）在伸手可及范围
- [ ] 联调 PC 与 Pepper **同一局域网**（建议直连或同 VLAN，避免跨网段 NAT/隔离）；记录 Pepper IP（机器人设置→网络，或路由器 DHCP 列表）
- [ ] 确认 Pepper 固件为 **NAOqi 2.9**（设置→关于本机）
- [ ] 已知 **开机免联网激活**（已确认），无需 SoftBank 账号，纯内网可长期运行

---

## §1 Python 2.7 运行环境

- [ ] 联调 PC 安装 **Python 2.7.18**（python.org 最后 2.7 版，ABI 须匹配 pynaoqi 的 .pyd）
      ```bat
      python2.7 --version
      :: 预期：Python 2.7.18
      ```
- [ ] SDK 包位置（工作区根，未纳入 git）：`D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013\`
- [ ] 设置环境变量（Windows cmd / bat）：
      ```bat
      set SDK=D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013
      set PYTHONPATH=%SDK%\lib
      set PATH=%SDK%\bin;%SDK%\lib;%PATH%
      ```
- [ ] 验证 import（**必须是 Py2.7 解释器**）：
      ```bat
      python2.7 -c "import qi, naoqi; print('qi+naoqi import OK')"
      :: 预期打印：qi+naoqi import OK
      ```
  - 失败排查：
    - `ImportError: No module named qi` → `PYTHONPATH` 未设对或 `%SDK%\lib` 路径错
    - `[WinError 126] 找不到指定的模块` / 加载 `qi.pyd` 失败 → `PATH` 未加 `%SDK%\bin`（虽 `bin/` 已含 `msvcr120/msvcp120.dll`，个别机器仍需在 PATH 上）

---

## §2 broker 连通性（`qi.Session().connect`）

- [ ] 连通性探活：
      ```bat
      python2.7 -c "import qi; s=qi.Session(); s.connect('tcp://<PEPPER_IP>:9559'); print('connected, services=', len(s.services()))"
      :: 预期：connected, services= <正整数>
      ```
- [ ] 或最小 proxy 探活：`s.service('ALMotion')` 返回 proxy 不抛异常
- **PASS 判据**：`connect` 无异常，且 `services()` 返回非空列表
- 失败排查：
  - `ConnectionRefused` → Pepper 未上电 / IP 错 / 端口非 9559
  - `timeout` → 跨网段或被实验室 VLAN 隔离 → 改为同网直连（文档实证 `--qi-url` 直连**无需开发者模式/IP 白名单**）

---

## §3 核心 proxy 可用性探测

逐条 `session.service('<proxy>')`，记录可用/不可用：

| proxy | 预期 | 失败处理 |
|---|---|---|
| `ALMotion` | ✅ 可用 | — |
| `ALRobotPosture` | ✅ 可用 | — |
| `ALAnimationPlayer` | ✅ 可用 | — |
| `ALBasicAwareness` | ✅ 可用 | — |
| `ALTabletService` | ✅ 可用 | — |
| `ALMemory` | ✅ 可用 | — |
| `ALAudioDevice` | ✅ 可用 | — |
| `ALDialog` / `ALTextToSpeech` | 存在但**禁用** | 不实例化，仅确认存在（改云端） |
| `ALNavigation` | ⚠️ 2.9 可能无纯 qi 的 ALNavigation | **降级项**，纯 qi 走 `ALMotion.moveTo`，不依赖 |
| `ALAutonomousLife` | ✅ 可用 | 联调期设为 `disabled`（见 §7） |

- **PASS 判据**：上列「✅ 可用」项全部 `service()` 成功；`ALNavigation` `service not found` 属预期（降级项，不影响）

---

## §4 麦克风音频链路（核心里程碑：`audio.py`）

- [ ] 启动桥：`python2.7 bridge.py --qi-url tcp://<PEPPER_IP>:9559`
      ```text
      预期启动输出：
      [bridge] connected to Pepper broker: tcp://<IP>:9559
      [bridge] IPC listening on 127.0.0.1:9560 (Py3 main gateway connects here)
      ```
- [ ] 用附录 A 的 Py3 测试客户端（或临时主网关）连 `127.0.0.1:9560`，下发 `{"id":2,"action":"audio_start","params":{}}`
      ```json
      预期回包：{"id":2,"ok":true,"result":{"audio":"started"}}
      ```
- [ ] 朝 Pepper 说话 → 桥持续上行音频帧：
      ```json
      {"type":"audio","rate":16000,"channels":1,"data_b64":"..."}
      ```
- 预期帧规格（NAOqi 通用，⚠️ 待真机确认精确值）：
  - `int16` PCM；NAOqi 默认每音频帧 **1366 个样本**（@16k ≈ 85ms）
  - 单声道每帧 ≈ 2.7KB；4 通道分离每帧 ≈ 10.9KB
- ⚠️ **真机实测确认项**（只改 `audio.py`，不影响 `bridge.py` 其余逻辑）：
  1. `setClientPreferences(name, rate, channels, deinterleave)` 中 `channels=1` 是否真为单声道混合（还是返回 4 通道）
  2. 回调 `value` 的实际类型（`str` / `buffer`）与每帧样本数
  3. 事件名 `ALAudioDevice/<name>` 在 2.9 是否与文档一致
- **PASS 判据**：朝麦克风发声后能稳定收到连续 `audio` 帧；`base64` 解码后字节数 ≈ `2 × 样本数 × 通道`
- 失败排查：
  - `audio_start` 报错 `service not found: ALAudioDevice` → 先回 §3 确认
  - 收不到帧 → 麦克风未订阅 / 事件名差异（⚠️ 项 3，仅改 `audio.py`）

---

## §5 动作原语冒烟（逐项下发）

用附录 A 客户端或主网关连 9560，逐项验证：

| action | 下发 | 预期 result | 注意 |
|---|---|---|---|
| `emote` | `{"action":"emote","params":{"animation":"Wave"}}` | `{"played":"Wave"}`，Pepper 挥手 | ⚠️ 动画标签在 2.9 路径可能不同，先试 `Wave` |
| `approach` | `{"action":"approach"}` | `{"approached":"user"}`，前移 0.3m | 先确认周围安全，距离可调 |
| `navigate` | `{"action":"navigate","params":{"goal":[0,0,0]}}` | 原地（x,y=0 不动） | 广场测试再给非零航点 |
| `tablet_render` | `{"action":"tablet_render","params":{"html":"<h1>你好</h1>"}}` | `{"tablet":"rendered"}`，平板显示文字 | 需 `ALTabletService` |
| `get_status` | `{"action":"get_status"}` | `{"posture":...,"audio_streaming":...}` | — |
| `stop_all` | `{"action":"stop_all"}` | `{"stopped":true}`，`killAllTasks` | **急停验证** |

- **PASS 判据**：`emote` / `approach` / `tablet_render` / `get_status` / `stop_all` 全部返回 `ok:true`
- ⚠️ 真机调参：`emote` 动画标签、`approach` 前移距离按礼仪/场地微调

---

## §6 端到端 IPC（替代主网关的最小验证）

- [ ] 用附录 A 的 Py3 测试客户端连 `127.0.0.1:9560`，循环发 `get_status` + `audio_start`，稳定打印回包与音频帧
- **PASS 判据**：JSON 行收发稳定、无断连、音频帧连续
- 注：正式 `suiyue-pepper` Py3 主网关尚未实现，本节用最小客户端替代，验证 IPC 协议本身

---

## §7 安全与降级（联调纪律，必读）

- [ ] 联调前确认 Pepper 周围 **1.5m 净空**，人员退至侧后，避免 `approach`/`navigate` 撞人
- [ ] 先验证 `stop_all` 急停可用，再跑动作
- [ ] `approach` / `navigate` 距离从 **0.3m 小步进**起；0.4 m/s 限速由 NAOqi 内部约束
- [ ] 联调期禁用 `ALAutonomousLife`（避免 NAOqi 自主行为抢控制权）：
      ```python
      session.service("ALAutonomousLife").setState("disabled")
      ```
- [ ] **不实例化** `ALSpeechRecognition` / `ALTextToSpeech` / `ALDialog`（改云端 FunASR + GPT-SoVITS）
- [ ] Pepper 自带**跌倒保护**（倾斜→kill motors）为硬件兜底，不依赖软件
- [ ] ⚠️ **失联看门狗（主网关断连 > N 秒 → 自动 `stop_all`）本版未实现**（见 `bridge.py`/`README.md` TODO）；本次仅手动验证 `stop_all`；**生产前必须补齐跨进程心跳**

---

## 附录 A：最小 Py3 联调客户端（`test_client.py` 片段）

复制为任意 `.py` 文件，用 **Python 3** 运行（桥侧是 Py2.7，IPC 用 utf-8 文本 JSON 行，两端文本模式即可）：

```python
# -*- coding: utf-8 -*-
import socket, json, time

s = socket.create_connection(("127.0.0.1", 9560))
sock_file = s.makefile("rw")  # 文本模式，JSON 行

def send(action, params=None, mid=1):
    sock_file.write(json.dumps({"id": mid, "action": action, "params": params or {}}) + "\n")
    sock_file.flush()

send("get_status", mid=1)
print("status:", sock_file.readline().strip())

send("audio_start", mid=2)
for _ in range(8):
    line = sock_file.readline().strip()
    if not line:
        break
    obj = json.loads(line)
    if obj.get("type") == "audio":
        print("audio frame b64 len:", len(obj["data_b64"]))
    else:
        print("resp:", line)

time.sleep(1)
send("audio_stop", mid=3)
print("audio_stop:", sock_file.readline().strip())
s.close()
```

---

## 附录 B：阻塞项收敛

- **已清零**：Py2.7 `naoqi` SDK 获取（2.5.7.1）、开机免联网激活、远程连接 IP 白名单（文档实证 `--qi-url` 直连无需）
- **本次联调目标**：
  1. 验证 `qi.Session().connect` 在 NAOqi 2.9 实际连通
  2. 实测 `audio.py` 回调签名/事件名/每帧样本数（⚠️ 项）
  3. 确认动作 proxy 命名（`emote` 动画标签、`approach` 距离等）
- **唯一剩余前提**：一台装 **Python 2.7** 的联调机 + 通电同网的 Pepper
- 联调结论回填：`pepper/naoqi_bridge/README.md` 的 TODO 清单（勾掉已验证项）
