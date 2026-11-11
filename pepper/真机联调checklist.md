# Pepper 真机联调 Checklist（NAOqi 2.5.10.7 + pynaoqi 2.5.7.1 桥）

> **背景**：Pepper 固件 NAOqi 2.5.10.7，端侧用 `pynaoqi-python2.7-2.5.7.1-win32-vs2013`（Py2.7-only）起 `qi-bridge` 子进程连 broker，Py3 主网关经本地 TCP:9560 IPC 派发动作原语、回收麦克风音频。已确认 **Pepper 开机免联网激活**，故 100% 内网可长期运行。
>
> **本文档用途**：在「一台装 Py2.7 的联调机 + 通电同网的 Pepper」就位后，照此逐项验证 `naoqi_bridge/` 的可运行性。所有带 ⚠️ 的项为代码按 NAOqi 2.5 文档形状编写、**未经真机验证**，需真机实测确认，是本次联调的核心目标。
>
> **关联文件**：`pepper/naoqi_bridge/{bridge.py,audio.py,README.md}`、`brain/capabilities/pepper_v1.yaml`、`docs/完成度评估.md`（G1–G10 缺口编号的权威定义）。
>
> **G 编号对照**：本 checklist 的 §8 / §9 分别对应 `完成度评估.md` 里的 **G3 / G4（跨组件契约）** 与 **G7–G10（真机专项验证）**；G1（注册 pepper-01）、G5（场景包加载器）、G6（`self.pepper.*` 工具面，暂不建议建）已完成或不涉及本 checklist。

---

## §0 硬件与网络前置

- [ ] Pepper 上电、立于平整无障碍区，物理急停按钮（后颈/底座）在伸手可及范围
- [ ] 联调 PC 与 Pepper **同一局域网**（建议直连或同 VLAN，避免跨网段 NAT/隔离）；记录 Pepper IP（机器人设置→网络，或路由器 DHCP 列表）
- [ ] 确认 Pepper 固件为 **NAOqi 2.5.10.7**（设置→关于本机）
- [ ] 已知 **开机免联网激活**（已确认），无需 SoftBank 账号，纯内网可长期运行
- [ ] 🔴 **关闭 `boot-config`（Getting Started Wizard）并持久化** —— 实测必做（2026-10-12）
      >现象：开机提示"连接服务器失败"；ssh 后 `stopBehavior boot-config` 即本地内网正常。
      > 关机向导（ALBehaviorManager 的 default behavior）会外连 Aldebaran 账号 + 检查更新，
      > air-gapped 下必失败，**且部分功能被阻塞**。
      ```bash
      qicli call ALBehaviorManager.isBehaviorRunning boot-config      # 确认在跑
      qicli call ALBehaviorManager.stopBehavior boot-config           # 立即关
      qicli call ALBehaviorManager.removeDefaultBehavior boot-config   # 持久化（否则重启复现）
      ```
- [ ] **PASS**：`removeDefaultBehavior` 后**重启**，开机无报错，
      且 `isBehaviorRunning boot-config` → `False`
- [ ] 关`ALAutonomousLife`（见 §7），否则会抢 `EMOTION_TO_ACTION` 的控制权

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
| `ALNavigation` | ⚠️ 本方案不依赖 ALNavigation（纯 qi 用 `ALMotion.moveTo`） | **降级项**，纯 qi 走 `ALMotion.moveTo`，不依赖 |
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
  3. 事件名 `ALAudioDevice/<name>` 在 2.5.x 是否与文档一致
- **PASS 判据**：朝麦克风发声后能稳定收到连续 `audio` 帧；`base64` 解码后字节数 ≈ `2 × 样本数 × 通道`
- 失败排查：
  - `audio_start` 报错 `service not found: ALAudioDevice` → 先回 §3 确认
  - 收不到帧 → 麦克风未订阅 / 事件名差异（⚠️ 项 3，仅改 `audio.py`）

---

## §5 动作原语冒烟（逐项下发）

用附录 A 客户端或主网关连 9560，逐项验证：

| action | 下发 | 预期 result | 注意 |
|---|---|---|---|
| `emote` | `{"action":"emote","params":{"animation":"Wave"}}` | `{"played":"Wave"}`，Pepper 挥手 | ⚠️ 动画标签在 2.5.x 路径可能不同，先试 `Wave` |
| `approach` | `{"action":"approach"}` | `{"approached":"user"}`，前移 0.3m | 先确认周围安全，距离可调 |
| `navigate` | `{"action":"navigate","params":{"goal":[0,0,0]}}` | 原地（x,y=0 不动） | 广场测试再给非零航点 |
| `tablet_render` | `{"action":"tablet_render","params":{"html":"<h1>你好</h1>"}}` | `{"tablet":"rendered"}`，平板显示文字 | 需 `ALTabletService` |
| `get_status` | `{"action":"get_status"}` | `{"posture":...,"audio_streaming":...}` | — |
| `stop_all` | `{"action":"stop_all"}` | `{"stopped":true}`，`killAllTasks` | **急停验证** |

- **PASS 判据**：`emote` / `approach` / `tablet_render` / `get_status` / `stop_all` 全部返回 `ok:true`
- ⚠️ 真机调参：`emote` 动画标签、`approach` 前移距离按礼仪/场地微调

---

## §6 端到端 IPC（先用最小客户端隔离协议层，再接主网关）

- [ ] **第一步（协议层）**：用附录 A 的 Py3 测试客户端（或 `pepper/test_bridge_client.py`）连 `127.0.0.1:9560`，循环发 `get_status` + `audio_start`，稳定打印回包与音频帧
      - **PASS 判据**：JSON 行收发稳定、无断连、音频帧连续
- [ ] **第二步（主网关链路）**：起正式主网关 `python3.13 gateway.py`（云端 xiaozhi WS + 桥 IPC 打通），确认心跳喂狗生效
      - 观察桥侧日志每 5s 收到一次 `ping`（`gateway_config.HEARTBEAT_INTERVAL_S=5.0`）
- **PASS 判据**：主网关运行时**持续**收到 `ping`；`kill` 主网关进程后，桥侧应在 **15s**（`WATCHDOG_TIMEOUT_S=15.0`）内打印 `[watchdog] 主网关心跳超时 15.0s -> 自动 stop_all`，且 Pepper 停止运动
- 注：主网关 `pepper/gateway.py`（Py3.13）与桥 `naoqi_bridge/bridge.py`（Py2.7）**均已实现**；本节先用最小客户端把协议层与硬件层解耦验证，再叠主网关，便于定位是哪一层出问题

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
- [ ] **失联看门狗（已实现，须实测）**：桥侧 `_start_watchdog` 线程监视主网关 `ping`，超过 `WATCHDOG_TIMEOUT_S=15.0` 未收到即自动 `stop_all`（ADR-011 §决策3）
      - 联调实测：起主网关 → 确认桥日志每 5s 收一次 `ping` → 手动结束主网关进程 → 桥应在 15s 内打印 `[watchdog] 主网关心跳超时 15.0s -> 自动 stop_all`
      - 手动 `stop_all` 仍须单独验证一次（不等心跳超时）
- [ ] 心跳周期 5s < 超时阈值 15s（`gateway_config.HEARTBEAT_INTERVAL_S=5.0` / `naoqi_bridge/config.py:29`），留 3× 余量，容忍单次丢包

---

## §8 跨组件契约（G3 / G4，**云端 xiaozhi server 配合才能定**）

> 这两项不在 Pepper 仓内，代码已写但**依赖云端确认**。§1–§7 全绿也不代表它们成立，需在打通云端 WS 后单独验证。

### G3 — emotion 信号契约（网关读不到情绪标签）

网关当前写法（`pepper/gateway.py:251`，⚠️ 未验证）：`msg.get("emotion") or msg.get("llm", {}).get("emotion")`——字段名依赖 server/LLM 版本。

- [ ] **抓实际下发结构**：在 `gateway.py` 打印/落盘一条 LLM 应答消息的完整 JSON，核对情绪标签的真实路径
      ```python
      # 临时在 gateway 收到 llm 消息处加：
      log.info("[G3] raw msg = %s", json.dumps(msg, ensure_ascii=False))
      ```
- [ ] **确认标签词表**：云端 LLM 实际输出的 emotion 取值是否命中 `pepper/gateway_config.py:47` `EMOTION_TO_ACTION` 的 **6 个键**（源码实测值）：
      `happy` / `excited` / `soothing` / `curious` / `concerned` / `neutral`
      → 未命中的标签会**静默回落到** `("posture", {"name":"Stand"})`（`gateway.py:351-352`），表现为"永远站着不动"，属静默失败
- [ ] 若不一致，二选一：
  - **[推荐]** 在 server 端约束 LLM 输出固定 emotion 标签（改 prompt / 配置，云端可控）
  - 改 `gateway.py` 解析路径 + 扩 `EMOTION_TO_ACTION` 键（端侧改，云零改但每次都要跟版）
- **PASS 判据**：云端返回一句带情绪的话，Pepper 做出**对应**的情绪动作（不只是"做了某个动作"）
- [ ] **失败排查**：标签缺失/不命中 → 走默认 `posture Stand` 不报错，但属**静默失败**（务必看日志确认 `emotion=xxx -> action ...` 这行真的打了，见 `gateway.py:355`）

### G4 — xiaozhi-server 设备绑定（大脑派发找不到目标）

- [ ] **确认 server 侧设备身份**：网关连 server 时 `device_id` 留空、按连接分配（`gateway.py:216`）。需在 server 侧确认这条连接被识别为 **Pepper**，而非随机分配
- [ ] **与大脑对齐**：大脑 `brain/mcp/config.yaml` 已注册 `pepper-01`；确认 server 侧的设备标识与之对应
- [ ] **反向验证**：在 server 会话里触发一次 `self.suiyue.emote(device_id="pepper-01")`，确认：
  1. MCP 工具返回成功（大脑认识这个设备）
  2. **Pepper 本体有反应**（说明 server → WS → 网关 → 桥 的下行链路通）
- **PASS 判据**：上面 2 条同时成立（返回成功 ≠ 本体会动，两条都要）
- **失败排查**：
  - 返回"未知设备" → 大脑侧未注册（已修，回归查 `config.yaml`）
  - 返回成功但 Pepper 不动 → 下行链路断（server 未把 MCP 结果推给该连接 / WS 绑定错设备），属 server 侧问题

---

## §9 真机专项验证（G7–G10，**只能上真机才能拍板**）

> 这四项在代码里都标了 ⚠️ 假设。§4/§5 是"顺带能验"，本节是**专项、逐条留证**。

### G7 — NAOqi 动画标签真实性

`pepper_cn_v1` 与 `EMOTION_TO_ACTION` 里写的动画名（`Wave` / `Crouch` / `head_tilt` 等）是**按文档假设**的，写错会静默失败。

- [ ] **列出真机可用动画**（最权威做法，先列再选）：
      ```bat
      python2.7 -c "import qi; s=qi.Session(); s.connect('tcp://<PEPPER_IP>:9559'); p=s.service('ALAnimationPlayer'); print(p.getAnimationNames())"
      ```
- [ ] 挑一个确认存在的动画（如 `Wave`）跑 `emote`，看 Pepper 是否真的动
- [ ] **校验 `processRemote` 回调签名与音频通道顺序**（代码假设：回调 `(value,)`、`value` 为 4 通道交织 buffer）——见 §4 的 ⚠️ 实测确认项 1/2
- [ ] 把真机实际动画名**回填** `gateway_config.py:47` `EMOTION_TO_ACTION` 与 `packs/pepper_cn_v1/agents/companion.yaml`
- **PASS 判据**：每个情绪标签都能让 Pepper 做出**可见且不同**的动作
- **失败排查**：`play` 返回成功但不动 → 动画名不存在（静默失败）；动作卡住 → 前一动作未结束，需先 `stop_all`

### G8 — TTS 下行真机扬声

当前默认语音路径：xiaozhi 下发回复文本 → 网关 `say_text` IPC → Pepper `ALTextToSpeech.say()`。
网关忽略云端 TTS 二进制音频；只有将 `PEPPER_LOCAL_TTS=0` 才走下方旧音频播放路径。

- [ ] **绕过云端单测扬声**（先隔离云端变量）：构造一段 16k 单声道 **裸 PCM**（base64）→ 经 IPC 下发 `audio_play`
      > ⚠️ 契约要点（源码锚定 `naoqi_bridge/bridge.py:138-144`）：`data_b64` 解码后是**裸 PCM 字节**，不是 WAV（WAV 头由 `audio.py:161 pcm_to_wav_bytes` 内部封装）；采样率字段名是 **`rate`**（不是 `sample_rate`）。

      ```json
      {"id":9,"action":"audio_play","params":{"rate":16000,"channels":1,"data_b64":"<裸PCM的base64>"}}
      ```
      ```bat
      :: 生成测试裸 PCM 并 base64（Py3，16k 单声道 1s 正弦）
      python -c "import math,struct,base64; pcm=b''.join(struct.pack('<h',int(8000*math.sin(i/20.))) for i in range(16000)); open('t.pcm_b64.txt','w').write(base64.b64encode(pcm).decode())"
      ```
- [ ] 确认回包 `{"id":9,"ok":true,"result":{"played":true}}`，且 Pepper **扬声器真的出声**（这一步最容易"返回 ok 但没声音"）
- [ ] **听感/参数观察**：有无爆音、延迟是否可接受、采样率是否需重采样（云端 GPT-SoVITS 常见 22050/32000 Hz）
- [ ] **打断行为**：TTS 播放中说话，确认上行音频能打断下行（网关已有此逻辑）
- **PASS 判据**：扬声器出声且内容正确；打断生效
- **失败排查**：无声 → 确认 `ALAudioDevice` 的扬声器通道号（`ALAudioPlayer.playToSpeaker` 的第二参）；采样率不匹配 → 在 `play_audio` 前加重采样

### G9 — 真机 Win x86 网关机 SDK import（VC120 运行时）

- [ ] **确认联调机是 Windows x86**（SDK 为 win32-vs2013，**ARM/树莓派不可用**）：
      ```bat
      python2.7 -c "import platform; print(platform.architecture(), platform.machine())"
      :: 预期：('32bit', 'Windows') 'AMD64'/'i386' 的 32 位 Python
      ```
- [ ] `python2.7 -c "import qi, naoqi"` 通过（详见 §1，此处强调 **VC120** = `msvcr120/msvcp120.dll`）
- [ ] `--auto-bridge` 能稳定拉起 Py2.7 桥子进程（跑 `start_pepper_debug.bat`，确认日志出现 `[bridge] connected`）
- [ ] Py2.7 与 Py3.13 **同机共存**互不干扰（两个解释器 PATH 顺序、`--auto-bridge` 用的 `PEPPER_PY2_EXE` 指向正确）
- **PASS 判据**：一条 `start_pepper_debug.bat` 从冷启动到"桥已连 broker + 网关已连云端"全绿
- **失败排查**：`[WinError 126]` → 缺 VC120 运行库或 `PATH` 未含 `%SDK%\bin`；找不到 `naoqi` 模块 → 装成了 Py3 版 SDK

### G10 — 巡游拓扑与禁区坐标（需 ALNavigation 建图）

`packs/pepper_cn_v1/mobility.yaml` 的 `patrol.points` 与 `safety.yaml` 的 geofence 禁区**目前是骨架占位**，需真机建图后填真实值。

- [ ] **建图**（NAOqi 无原生虚拟墙，用 ALNavigation 禁区 + 限速 0.4 m/s 近似）：
      ```python
      # 录制地图（遥控 Pepper 走遍巡游区域与禁区边界）
      session.service("ALNavigation").startExploration()
      # 走完后
      session.service("ALNavigation").stopExploration()
      session.service("ALNavigation").saveMap("pepper_patrol_map")   # 存到 Pepper 持久化目录
      ```
- [ ] **取巡游点位**：从地图上取若干拓扑节点（沙发边/餐桌边/床头），得到 `marker_id` 或坐标，填 `mobility.yaml: patrol.points`
- [ ] **划禁区**：在地图上把楼梯口/门槛/桌角等划为禁区，填 `safety.yaml: geofence`
- [ ] **实测巡游**：`navigate` 到各点位一次，确认可达（NAOqi 导航精度弱于大亮 SLAM，**限速 0.4 m/s**）
- [ ] **禁区生效验证**：尝试 `navigate` 到禁区点，应被拒或绕行
- **PASS 判据**：巡游点位全部可达；禁区点不可进入
- **失败排查**：地图未保存 → `saveMap` 抛异常（需先 `ALNavigation` 已加载地图）；点位不可达 → 地图未覆盖该区域，补录

---

## §10 联调结论回填（收尾别忘）

- [ ] 把 §8/§9 每项的**实测结论**回填：
  - `pepper/naoqi_bridge/README.md` 的 TODO 清单（勾掉已验证项）
  - `docs/完成度评估.md` §4 的 G3/G4/G7–G10 状态（已完成 → 更新）
  - 真机实测到的动画名/采样率/坐标，回填 `gateway_config.py`、`packs/pepper_cn_v1/*.yaml`
- [ ] 若某项结论与代码假设不符 → 改代码 + 在本 checklist 该项下写一行"实测：xxx（原假设 yyy 已修正）"

---

## 附录 A：最小 Py3 联调客户端（`test_client.py` 片段）

> 仓库已有现成实现：**`pepper/test_bridge_client.py`**（不依赖 Py2 SDK，可直接用 Py3 跑，支持全部动作原语 + 音频帧校验）。下面的片段仅作协议最小示例，或在需要临时改脚本时用。
> 桥侧独立调试用 `pepper/pepper_bridge.bat` 起桥，`pepper_gateway.bat` 起主网关。

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
  1. 验证 `qi.Session().connect` 在 NAOqi 2.5.10.7 实际连通
  2. 实测 `audio.py` 回调签名/事件名/每帧样本数（⚠️ 项）
  3. 确认动作 proxy 命名（`emote` 动画标签、`approach` 距离等）
- **唯一剩余前提**：一台装 **Python 2.7** 的联调机 + 通电同网的 Pepper
- 联调结论回填：`pepper/naoqi_bridge/README.md` 的 TODO 清单（勾掉已验证项）

---

## 附录 C：一键启动脚本（替代手工两条命令）

`pepper/` 下新增联调启动脚本，省去手工设环境变量：

| 脚本 | 用途 |
|---|---|
| `start_pepper_debug.bat` | **一键启动**：设 SDK 环境 → 校验 Py2.7 import → 用 `--auto-bridge` 连主网关（自动拉起 Py2.7 桥）。窗口内 Ctrl+C 先 `stop_all` 再退出（桥子进程一起结束） |
| `pepper_bridge.bat` | 只起 Py2.7 桥（调试/IPC 验证用，配合 `test_bridge_client.py`） |
| `pepper_gateway.bat` | 只起 Py3 主网关（需桥已在 `:9560` 监听） |
| `stop_pepper_debug.bat` | 兜底关窗（独立窗口模式用） |

可用环境变量覆盖配置（详见脚本头注释）：`PEPPER_SDK_ENV` / `PEPPER_IP_ENV` / `SUIYUE_CLOUD_WS` / `PEPPER_PY2_EXE` / `PEPPER_PY3_EXE` / `PEPPER_DEVICE_ID` / `PEPPER_INSTALL_DEPS=1`。
