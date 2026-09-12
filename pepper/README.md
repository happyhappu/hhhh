# Pepper 端侧网关（suiyue-pepper）

> 第四本体接入方案。与大亮（ADR-009）同一范式：**一个 body-driver 网关 + 能力注册表条目（pepper_v1.yaml）+ 场景包（pepper_cn_v1/）**，云端零改动。
> 上游形态参考 `docs/adr/ADR-002-三本体一脑.md`（已升级为四本体）、`ADR-011-全离线部署基线.md`。

## 1. Pepper 是什么（事实底座）

| 维度 | 规格 |
|---|---|
| 形态 | 人形，**1.2m 高 / 三轮全向底盘**（不能爬台阶，最大 ~0.4 m/s） |
| 自由度 | **20 DOF**（头/臂/手/轮），表达力强于大亮的 5 DOF |
| 主屏 | **10.1" 平板**（Android，可 WebView 渲染 companion UI） |
| 麦克风 | 4 个（头 2 + 耳 2），远场拾音 |
| 扬声器 | 2 个 |
| 摄像头 | 2 RGB + **3D 深度（额头红外）**，可用作在场/人脸/深度 |
| 主板 | x86 嵌入式级（Intel Atom 类），**算力弱** |
| 操作系统 | **NAOqi 2.9**（Linux 中间件；官方 `qi` Python SDK **仅 Python 2.7**） |
| 通讯 | Wi-Fi 2.4G/5G；局域网 `tcp://<ip>:9559` 的 NAOqi broker |
| 导航 | **ALNavigation**（拓扑地图，需人工建图；非 SLAM 精度） |
| 制造商 | SoftBank Robotics（Aldebaran） |

**核心判断**：Pepper 机载算力跑不动 8B LLM，且 NAOqi 中文 ASR/TTS 弱——因此 Pepper 在我们系统里是一个**纯瘦客户端**：把麦克风音频转给云端 xiaozhi，把云端 GPT-SoVITS 的 TTS 音频从扬声器放出，用 NAOqi 执行动作/导航/平板。**不增加 4090 显存预算**（ADR-011 §决策 2 不变）。

## 2. 接入架构（复用 client-py + 大亮网关两套范式）

```
[ Pepper 本体 (NAOqi) ]
   ├─ 麦克风 → Opus 编码 → WS 上行 → xiaozhi-esp32-server（ASR→LLM→TTS）
   ├─ 扬声器 ← TTS 流式下行（GPT-SoVITS 克隆女声，禁用 Pepper 内置 TTS）
   ├─ ALMotion/ALRobotPosture/ALAnimationPlayer ← self.pepper.emote（情感→动作）
   ├─ ALNavigation                                ← self.pepper.navigate/approach/patrol
   └─ ALTabletService                             ← self.pepper.tablet_render（companion Web UI）
        │
        └─ suiyue-pepper 网关（Python 3 主进程，跑在实验室服务器/同网 SBC）
              ├─ WS 连云端大脑（与 otto/reachy 同协议）
              └─ 本地 IPC → qi-bridge（Python 2.7 子进程，连 Pepper NAOqi broker :9559）
```

> 网关**不必跑在 Pepper 上**（Pepper 机载弱）：跑在实验室服务器或常开树莓派均可，只要求与 Pepper 同局域网。这与 chassis-gateway「外移到常开设备」的思路一致（ADR-011 §决策 3）。
>
> **NAOqi 版本决策（2026-09-11）**：当前为 **NAOqi 2.9**，可升级到 NAOqi 3（Android 基座 + QiSDK，Java），但**不升级**——升级路线需安卓/Java 开发，而我方技术栈为 Python、暂无安卓开发经验。故保持 2.9：用官方 `qi` Python SDK（**仅 Python 2.7**）在实验室服务器上起一个轻量 **`qi`-bridge 子进程**连接 Pepper broker，`suiyue-pepper` Python 3 主网关经本地 IPC（WebSocket / Unix socket）与桥通信。整个大脑逻辑仍是 Python 3，2.7 仅作末端协议桥。

## 3. 与现有三本体的差异点

| 维度 | Otto | Reachy Mini | 大亮 | **Pepper** |
|---|---|---|---|---|
| 形态 | 20cm 双足 | 28cm 桌面 | 1.56m 双轮人形 | **1.2m 三轮人形** |
| 主控/OS | ESP32 RTOS | 树莓派5 Linux | RK3588 Android | **x86 + NAOqi** |
| 移动 | 无 | 无 | 双轮 SLAM ±2cm | **三轮 ALNavigation 拓扑图** |
| 自由度 | 4–6 舵机 | 6-DOF 头 | 5 | **20** |
| 屏 | 1.54" | 4.3–5" 外加 | 11.6"+5–8" | **10.1" 平板** |
| 端侧 LLM | 否 | 否 | 否（阶段 C 才研讨） | **否（机载算力不足）** |
| 协议 | xiaozhi WS | xiaozhi WS | WS/MQTT + WS | **xiaozhi WS + NAOqi broker** |

Pepper 介于 Reachy（桌面）与大亮（全功能移动服务）之间：**有移动 + 有平板 + 20 DOF 表达**，但导航精度与载重弱于大亮。定位为**教学/展示级移动人形**。

## 4. 离线要点（air-gapped，见 ADR-011）

1. **禁用 Pepper 内置云端服务**：`ALSpeechRecognition` / `ALTextToSpeech` / `ALDialogue` 一律不用，改云端 xiaozhi + GPT-SoVITS；
2. **关闭 NAOqi 遥测与自动更新检查**（机箱外连 SoftBank），否则断网后反复重试超时；
3. **预装本地中文语音包**（若 Pepper 镜像自带 pico/nuance 中文 voice 则留作兜底，但主链路仍用 GPT-SoVITS）；
4. **ALNavigation 地图本地建好**，离线不依赖任何云端地图服务；
5. Pepper 本身不消耗 4090 显存；断网验收同 OFFLINE-CHECKLIST.md 阶段 4。

## 5. 安全（见 ARCHITECTURE §6）

- Pepper **自带防跌倒**：机身倾斜即切断电机，比大亮多一层硬件兜底；
- 但**失联停运动看门狗仍须有**：网关与云端断连 > N 秒 → `self.pepper.stop_all`（ALMotion.killAllTasks + 回 Stand）；
- NAOqi 无原生虚拟墙，用 **ALNavigation 禁区 + 限速 0.4 m/s** 近似 geofence（卧室/卫生间禁入）。

## 6. 目录占位与待办

```
suiyue/pepper/
├── README.md                 # 本文件
├── naoqi_bridge/             # Python 2.7 qi SDK 桥（音频/动作/导航/平板）
│   ├── bridge.py             # 主入口：连 broker(:9559) + 本地 TCP IPC 派发 + 急停
│   ├── audio.py              # 麦克风采集（ALAudioDevice/ALMemory 事件，培训文档 2-3 节）
│   └── README.md             # 运行环境 / IPC 协议 / 动作原语映射
└── packs/pepper_cn_v1/       # ★ 待建：场景包（镜像 daliang_cn_v1 的可选层）
```

### P0 · 阻塞启动（类比大亮 D6）
- [x] Pepper 固件 **NAOqi 2.9** 已确认，保持不升级（升级 NAOqi 3 = Android/QiSDK/Java，缺安卓开发能力）；
- [x] **Python 2.7 `qi` SDK 包已获取**（本地 `pynaoqi-python2.7-2.5.7.1-win32-vs2013/`，构建版本 **2.5.7.1**，VC120/VS2013 运行时，`bin/` 已含 msvcr120.dll 可干净加载）；SDK 同时暴露 `import qi`（lib/qi 包）与 `import naoqi`（lib/naoqi.py · ALProxy）两套 API；
- [ ] 确认本地**中文语音包 / 中文字体**是否已预装（离线兜底用）；
- [x] 确认 `tcp://<ip>:9559` 实验室局域网可达；培训文档实证 `--qi-url` 直连**无需 IP 白名单/开发者模式**（P4 降级为真机验证项）；
- [x] **Pepper 开机无需联网激活**（用户已确认）→ air-gapped 前置条件满足，无 SoftBank 账号激活依赖；见尽调清单 Q 节已闭环。

### SDK 本地化运行环境（Py2.7 桥）
- SDK 路径：`../../pynaoqi-python2.7-2.5.7.1-win32-vs2013/`（工作区根，未纳入 git；运行前 `lib`→PYTHONPATH、`bin`+`lib`→PATH）。
- 启动桥（Windows）：
  ```bat
  set PYTHONPATH=<sdk>\lib
  set PATH=<sdk>\bin;<sdk>\lib;%PATH%
  python2.7 pepper\naoqi_bridge\bridge.py --qi-url tcp://<pepper-ip>:9559
  ```
- 连接用 `qi.Session().connect(...)`（或 `from naoqi import ALProxy`）；`bin/` 内 msvcr120/msvcp120 已随包，干净 Windows 可直接 import，无需另装 VS2013 运行库。
- ⚠️ 该 SDK 为 **Py2.7 构建**：桥子进程必须用 Python 2.7 解释器运行；主网关仍 Py3.13，二者经本地 WebSocket IPC 通信（见 §2 架构）。

### P1 · 阶段 A 工程准备
- [x] `naoqi_bridge/` 骨架已建（bridge.py + audio.py + README）；下一步**真机联调**跑通音频链路（见 `naoqi_bridge/README.md` TODO）；
- [ ] 云端加 `pepper_cn_v1` 场景包骨架 + `t_device_registry` 加 `pepper_v1` 条目；
- [ ] 演示：老人说"岁悦过来坐坐" → Pepper `self.pepper.approach` + 挥手 + 平板问候语；与 Otto/Reachy/大亮同台。

> Pepper 接入验证「端侧 OS 透明」原则（D2）再次成立：云端只认 xiaozhi 协议 + MCP，不知背后是 RTOS / Linux / Android / NAOqi。

## 7. 官方 SDK 培训文档核对（NAOqi 2.5 大学培训文档）

已对照《NAOqi Python SDK 大学培训文档》（148 页，基于 NAOqi **2.5**）逐章核对，对 §2 架构与能力注册表的支撑/修正如下：

- **代际一致**：文档基于 NAOqi 2.5（链接 `pepper-naoqi-25`），与本方案锁定的 **2.9 同属 legacy NAOqi 代**，API 命名与连接方式一致 → 2.9 不升级到 3 的决策稳。
- **Python 2.7 铁证**：文档示例脚本首行 `#!/usr/bin/env python2.7`（ROS 章节 rospy 节点）→ 官方 `qi` SDK 确为 **Py2.7 only**，末端 Py2.7 qi-bridge 路线正确。
- **连接方式 = `--qi-url` 直连**：所有示例 `python xxx.py --qi-url pepper.local（或 Pepper IP）` 经**局域网直连**，文档**无"开发者模式 / IP 白名单 / 防火墙"**要求 → 收敛尽调清单 P4（远程连接硬阻塞）为"真机 2.9 验证即可"。
- **音频链路印证**：`audio_record.py` 经局域网把 Pepper 麦克风录成 **WAV** 传到本地 PC（2-3 节）→ 正是 `naoqi_bridge/audio.py` 要做的事（Pepper 麦克风 → 本地 → 云 FunASR）。
- **核心 proxy 实证命名**（已校准 `pepper_v1.yaml`）：ALMemory / ALMotion / ALRobotPosture / ALAnimationPlayer / ALBasicAwareness / ALAudioRecorder / ALSoundLocalization / ALFaceDetection / ALPeoplePerception / ALTracker / ALTabletService / ALDialog / ALTextToSpeech / ALAnimatedSpeech / ALAutonomousLife。
- **禁用 ALAutonomousLife（新增）**：云端显式控制架构下必须置 `disabled/nonAutonomous`，否则 NAOqi 自主行为会与动作指令冲突。
- **导航走 ROS**：文档第 5 章"导航"实际是 **ROS 路线**（`naoqi_driver` + ROS Kinetic + Gmapping/AMCL/move_base），非纯 `qi` 的 ALNavigation。本方案不引入 ROS，纯 qi 路径用 `ALMotion.moveTo` + 基础避障；ALNavigation 拓扑导航列为**可选降级**，待真机 2.9 验证。
- **视觉/人脸**：ALFaceDetection + ALPeoplePerception 经局域网传画面到本地 PC（3 章）→ 与"视觉上云/本地处理"一致。
- **SDK 版本对齐（新增）**：已获取官方 `pynaoqi-python2.7-2.5.7.1-win32-vs2013`（**2.5.7.1** 构建，Py2.7，VC120）。版本号 `2.5.7.1` 指 **pynaoqi 构建号**，与机器人固件 **NAOqi 2.9** 跨代兼容；本方案用到的标准模块（ALMotion/ALTextToSpeech/ALDialog/ALAudioRecorder/ALTabletService 等）在 2.5→2.9 间 API 稳定。个别 2.9 新增模块若不在该 SDK 中，真机连接时 `service not found`，列为**真机验证项**而非阻塞。
