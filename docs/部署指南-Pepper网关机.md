# Pepper 网关机部署指南（Windows → 跑起来）

> **这台机器是什么**：Pepper 的**网关机**，跑两个进程——
> ① Py2.7 的 `naoqi_bridge`（连 Pepper 机器人）② Py3 的主网关（连 4090 云端）。
>
> **它不跑任何 AI 模型**（LLM/ASR/TTS 全在 4090 上），只做 **音频 I/O + 动作派发**。
> 所以**这��机器很轻**，不需要 GPU、不需要 Docker（详见 §4）。
>
> **依据**：`pepper/README.md` + `pepper/真机联调checklist.md` + **实测 SDK 目录内容**
> 与 `xiaozhi-esp32-server` 源码核实。

---

## 1. 操作系统：装哪个版本

### ✅ 结论：**Windows 10 或 11（64 位）+ 装 32 位 Python 即可**

| 项 | 要求 | 说明 |
|---|---|---|
| **系统版本** | Windows 10 / 11 **64 位**（x64） |❌ **不要装 32 位 Windows** |
| **CPU** | 任意 x86_64（Intel/AMD） | ❌ **ARM 不行**（树莓派、骁龙等） |
| **Python 2.7** | **必须是 32 位**（x86） | SDK 是 `win32-vs2013` 构建 |
| **Python 3.13** | **建议 32 位**（与Py2.7 同架构） | `websocket-client` 是纯 Python，无ABI 问题 |

> 🔴 **最关键的一条**：**pynaoqi SDK 是 32 位专用**（`pynaoqi-python2.7-2.5.7.1-win32-vs2013`）。
> 这决定了 **Py2.7 必须装 32 位版**，也意味着整台机的 Python 生态都要走 32 位。
> 但**操作系统本身可以是 64 位** —— 在 64 位 Windows 上装 32 位 Python 完全正常，
> 两者通过注册表 `Wow6432Node` 共存，互不干扰。
>
> ⚠️ **不要装 32 位 Windows**：没必要，且省不了内存（我们要跑的进程很轻）。

---

## 2. 软件清单

### 2.1 必装

| 软件 | 版本 | 用途 |
|---|---|---|
| **Python 2.7** | **2.7.18 x86（32 位）** | 跑 `naoqi_bridge`（连 Pepper） |
| **Python 3** | 3.13 **x86（32 位）** | 跑主网关 `gateway.py` |
| **pynaoqi SDK** | 2.5.7.1 win32-vs2013 | NAOqi 官方 SDK（**已下载**，见 §5） |

### 2.2 不需要装

| 软件 | 为什么不需要 |
|---|---|
| **Docker** | 见 §4 |
| **VC++ 2013 运行库** | ✅ **SDK 自带** `msvcr120.dll` / `msvcp120.dll` |
| **.NET Framework** | 两个脚本都不用 |
| **Node.js / Java** | 与本项目无关 |
| **CUDA / 显卡驱动** | 这台机器不跑 AI 模型 |

### 2.3 可能要装（视情况）

| 软件 | 何时需要 |
|---|---|
| **opus 32 位库**（`libopus.dll`） | 🔴 **大概率需要**，见 §6.1 |
| VC++ 2013 x86 运行库 | 仅当仍报 `[WinError 126]` |
| 7-Zip / 解压工具 | 装Python 时用 |

---

## 3. 两个 Python 怎么配共存

### 3.1 核心原则：**靠绝对路径区分，不靠 PATH**

PATH 里放谁会互相打架。**我们的方案是完全不依赖 PATH 顺序**：

```
Py2.7  ← 只给naoqi_bridge 用，脚本里用绝对路径显式指定
Py3    ← 主网关用，日常命令行就用它
```

### 3.2 安装建议

| | Py2.7 | Py3.13 |
|---|---|---|
| 安装包 | `python-2.7.18.x86.msi` | `python-3.13.x.x-win32.exe` ← ⚠️ **注意选 x86** |
| 安装选项 | **勾 `pip` + `py launcher`** | **勾 `pip`**，建议**不要**勾 "Add to PATH" 以外的额外项 |
| 装完验证 | `C:\Python27\python.exe -c "import platform;print(platform.architecture())"` → 应为 `('32bit', 'Windows')` | `C:\Python313\python.exe -V` |

> ⚠️ **Py3 一定要选 win32（32 位）安装包**。官网默认给的是 64 位，
> 装错会出现"32 位 SDK 在 64 位 Python 里能用吗"的假象——
> `pynaoqi` 的 `.pyd` 是 32 位，**在 64 位 Py3 下会 ImportError**。

### 3.3 环境变量（SDK 相关）

**只设这3 个，且只对启动脚本的窗口生效**（脚本 `start_pepper_debug.bat` 会自动设，
手工启动时才需手动）：

```bat
set SDK=D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013
set PYTHONPATH=%SDK%\lib
set PATH=%SDK%\bin;%SDK%\lib;%PATH%
```

| 变量 | 指向 | 为什么 |
|---|---|---|
| `PYTHONPATH` | `%SDK%\lib` | 让 Py2.7 能 `import qi` / `import naoqi` |
| `PATH` | `%SDK%\bin` | 🔴 **必须**—— `.pyd` 依赖 `bin/` 里的 `qipython.dll` 等 90+ 个 DLL |

> 💡 `bin/` 与 `lib/` 下**各有**一份全套DLL（实测各 ~90 个），
> 两个都加进 PATH 更保险。

### 3.4 验证（**必做**）

```bat
:: ① Py2.7 能 import SDK
set SDK=D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013
set PYTHONPATH=%SDK%\lib
set PATH=%SDK%\bin;%SDK%\lib;%PATH%
C:\Python27\python.exe -c "import qi, naoqi; print('sdk OK')"
:: 预期：sdk OK

:: ② Py3 依赖
C:\Python313\python.exe -m pip install -r suiyue\pepper\requirements.txt
C:\Python313\python.exe -c "import websocket; print('ws OK')"
```

| 报错 | 原因 | 处置 |
|---|---|---|
| `ImportError: No module named qi` | `PYTHONPATH` 未设或路径错 | 检查 `%SDK%\lib` 是否存在 |
| `[WinError 126] 找不到指定的模块` | `PATH` 未含 `%SDK%\bin`（`.pyd` 加载不到依赖 DLL） | 把 `%SDK%\bin` 加进 PATH |
| `DLL load failed ... %1 不是有效的 Win32 应用程序` | 🔴 **Py3 装成 64 位了** | 重装 32 位 Py3 |

---

## 4. 需要 Docker 吗？—— **不需要**

**明确结论：Pepper 网关机不需要 Docker。**

| 判据 | 本机情况 |
|---|---|
| 是否跑 AI 模型？ | ❌ 不跑（LLM/ASR/TTS 全在 4090） |
| 是否需要 GPU？ | ❌ 不需要 |
| 依赖几个 Python 包？ | ✅ **1 个必装**（`websocket-client`）+ opus 时多1 个（`opuslib`） |
| 是否要装 CUDA/torch？ | ❌ **不需要**（省几个 GB） |

**Docker 的代价 vs 收益**：

| | 说明 |
|---|---|
| 代价 | Py2.7 + 32 位 x86 的 Docker 镜像在 Windows 上支持很差（Windows 容器不默认支持 32 位）；镜像构建麻烦 |
| 收益 | ≈0（就2 个依赖，用 venv 更轻） |

>💡 **正确的做法**：
> - 4090 上（Linux）**可以用 Docker**（要跑 torch/GPU）
> - 网关机上（Windows）**直接跑原生脚本**，用 `.bat` 一键启动
>
> 项目已经准备好了4 个 `.bat`（见 §7），就是为"不装 Docker"设计的。

---

## 5. 部署什么（内容很少）

> ✅ **好消息**：**不用从网上下载任何东西**。SDK 与代码都已在本地。

```
D:\WorkBuddy\桌面陪伴机器人\
├── pynaoqi-python2.7-2.5.7.1-win32-vs2013\   ← SDK（已就位，bin/lib/share 齐全）
├── suiyue\                                   ← 本项目源码（git 仓）
│   └── pepper\
│       ├── gateway.py                ← Py3 主网关（连 4090）
│       ├── gateway_config.py         ← 配置
│       ├── requirements.txt          ← Py3 依赖（2 个包）
│       ├── naoqi_bridge\             ← Py2.7 桥（连 Pepper）
│       │   ├── bridge.py
│       │   └── config.py
│       ├── start_pepper_debug.bat    ← ★一键启动（推荐）
│       ├── pepper_bridge.bat         ← 只起 Py2.7 桥（调试用）
│       ├── pepper_gateway.bat        ← 只起 Py3 主网关
│       └── stop_pepper_debug.bat     ← 兜底关窗
└── xiaozhi-esp32-server-0.9.7\       ← ⚠️ 这份不用管，它部署在 4090 上
```

### 部署动作（3 步）

- [ ] **确认 SDK 在位**（已就位，确认即可）
- [ ] **装两个 Python**（§3）
- [ ] **装 Py3 依赖**：`C:\Python313\python.exe -m pip install -r suiyue\pepper\requirements.txt`

> ⚠️ **不需要**改任何配置文件。`gateway_config.py` 里的默认地址
> （云端 WS `ws://192.168.31.10:8000/xiaozhi/v1`、机器人 `pepper.local:9559`）可以用
> **环境变量覆盖**，不必改代码。

---

## 6. SDK 目录名能不能改？—— ✅ 能，零代码改动

> **实测验证（2026-10-12）**：把SDK 目录临时改名为 `naoqi-sdk`，
> 确认 ① 脚本默认路径立即失效 ② 设 `PEPPER_SDK_ENV` 后`bin`/`lib` 完全可用
> ③ 改名不影响 SDK 内容（`bin/` 90 项、`lib/` 94 项、`share/` 1 项完整）。

### 6.0 推荐做法：改名 + 设一次环境变量

```bat
ren "D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013" naoqi-sdk

:: ① 永久生效（写进系统环境变量，只需设一次）
setx PEPPER_SDK_ENV "D:\WorkBuddy\桌面陪伴机器人\naoqi-sdk"

:: ② 本次窗口立即生效（setx 只对**新开**的窗口有效）
set PEPPER_SDK_ENV=D:\WorkBuddy\桌面陪伴机器人\naoqi-sdk
```

**为什么这样零成本**：`start_pepper_debug.bat:29-30` 与 `pepper_bridge.bat:12-13`
都是「**默认值 + 环境变量覆盖**」的两段式设计：

```bat
set "PEPPER_SDK=%WS_ROOT%\pynaoqi-python2.7-2.5.7.1-win32-vs2013"   :: 默认值
if defined PEPPER_SDK_ENV set "PEPPER_SDK=%PEPPER_SDK_ENV%"           :: 覆盖生效
```

> ⚠️ `pepper_gateway.bat` **不含 SDK 路径**（纯 Py3 主网关），
> 所以改名对它**完全无影响**。

### 6.1 哪些地方会失效 / 哪些不受影响

| 对象 | 改名后 | 说明 |
|---|---|---|
| `start_pepper_debug.bat` | 🔴 **失效**（找不到 SDK 会 `[ERROR]` 退出） | 设 `PEPPER_SDK_ENV` 即可 |
| `pepper_bridge.bat` | 🔴 同上 | 同上 |
| `pepper_gateway.bat` | ✅ **不受影响** | 纯 Py3，不碰 SDK |
| `gateway.py` / `bridge.py`（Python 代码） | ✅ **不受影响** | 从**环境变量**取路径，代码里无硬编码 |
| `.gitignore` / git 追踪 | ⚠️ 若改到 `suiyue/` **内部**需留意 | 见 §6.2 |

> 💡 **实测结论**：Python 代码（`gateway.py` L435 只是把 `pepper_dir` 加进
> `PYTHONPATH`）**没有任何 SDK 路径硬编码**。SDK 路径**只存在于两个 .bat 的默认值里**，
> 且都支持环境变量覆盖 → **改名不会破坏任何代码逻辑**。

### 6.2 ⚠️ 唯一要注意的：别把 SDK 挪进 `suiyue/` 仓库

`suiyue/` 是 git 仓库，而SDK 是**外部二进制**（未纳入 git）。若改名为 `naoqi-sdk`
并**移进 `suiyue/` 内部**，会被 `git add .` 收编 → 仓库体积暴涨。

**推荐**：保持在工作区根（`桌面陪伴机器人\`）下，只改目录名，**不进仓库**。

### 6.3 手工启动时的写法（不用 .bat）

```bat
set PEPPER_SDK_ENV=D:\WorkBuddy\桌面陪伴机器人\naoqi-sdk
:: 或直接用 set SDK=...（你的新路径）
set PYTHONPATH=%PEPPER_SDK_ENV%\lib
set PATH=%PEPPER_SDK_ENV%\bin;%PEPPER_SDK_ENV%\lib;%PATH%
C:\Python27\python.exe -c "import qi, naoqi; print('sdk OK')"
```

### 6.4 文档里的旧路径要不要一起改？

以下文档**只是说明文字**，运行时不影响，但为免误导建议顺手更新（也可不改）：

| 文件 | 位置 |
|---|---|
| `pepper/naoqi_bridge/README.md` | L35 / L39 |
| `pepper/README.md` | L56 / L114 / L120 |
| `pepper/真机联调checklist.md` | L41 / L44 |
| `brain/capabilities/pepper_v1.yaml` | L23 `sdk_path`（纯记录） |
| `docs/物理部署图.html` | L266 |
| `docs/OFFLINE-MATERIALS.md` | L157 |

> 💡 `brain/capabilities/pepper_v1.yaml` 的 `sdk_path` 是**能力注册表的声明字段**，
> 供人看与大模型参考，**没有任何代码读它来定位 SDK** → 改了也不会坏。

---

## 7. 音频依赖（🔴 最可能卡住的地方）

### 7.1 opus —— 必须解决

**实测结论（2026-10-12）**：核实 `xiaozhi-server/core/connection.py:119`：

```python
self.audio_format = "opus"    # 全文件仅此一处，不接受 hello 协商
```

→ **server 端写死 opus**，所以主网关**必须能编解码 opus**，否则音频链路起不来。

⚠️ **原文档说"可设 `PEPPER_AUDIO_FORMAT=raw` 绕过"是错的** —— server 不接受协商，
设 raw 会导致握手能成但**音频全部无效**。

**解决步骤**：

```bat
::① 装 opuslib（纯 ctypes 包装）
C:\Python313\python.exe -m pip install opuslib

:: ② 需要一个 32 位的 libopus.dll 放到 PATH（opuslib 靠 ctypes 加载它）
::    来源：https://opus-codec.org/downloads/ （32 位构建）
::    放到 C:\Python313\Lib\site-packages\opuslib\ 或任何 PATH 目录
```

验证：
```bat
C:\Python313\python.exe -c "import opuslib; e=opuslib.Encoder(16000,1,'voip'); print('opus OK')"
```
- 打印 `opus OK` → ✅ 编解码可用
- `OSError: could not load library` → 🔴 **缺 32 位 libopus.dll**，音频链路不可用

> 💡 **兜底方案**：若实在拿不到 32 位 libopus.dll，可暂时
> `set PEPPER_AUDIO_FORMAT=raw` 先验证**握手 + 动作派发**链路通不通
> （动作能跑、就是没声音），**但语音功能必须等opus 解决后才能用**。

### 7.2 音频链路说明（谁做什么）

```
Pepper 麦克风
  → naoqi_bridge (Py2.7)：ALAudioDevice 录音 → 裸 PCM
  → IPC TCP 127.0.0.1:9560（JSON行，base64 编码的 PCM）
  → gateway.py (Py3)：PCM → **opus 编码** → WS 上行
  → 4090 xiaozhi-server：opus 解码 → FunASR 识别
```

> 💡 **PCM 的格式约定**（实测源码 `naoqi_bridge/bridge.py:138-144`）：
> `data_b64` 解码后是**裸 PCM**（不是 WAV），采样率字段名是 **`rate`**。

---

## 8. 启动

### 8.1 首次启动前：关掉 boot-config（**必做**）

> 🔴 Pepper 开机时会报"连接服务器失败"——这是 `boot-config`（Getting Started Wizard）
> 在外连 Aldebaran 账号。**每次重启都要处理一次**，除非做持久化。

```bash
ssh nao@<PEPPER_IP>
qicli call ALBehaviorManager.isBehaviorRunning boot-config
qicli call ALBehaviorManager.stopBehavior boot-config
qicli call ALBehaviorManager.removeDefaultBehavior boot-config   # ★持久化，否则重启复现
qicli call ALAutonomousLife.setState disabled                  # 联调纪律，防抢控制权
```

### 8.2 一键启动（**推荐**）

```bat
cd D:\WorkBuddy\桌面陪伴机器人\suiyue\pepper

:: 用环境变量覆盖默认地址（不改代码）
set PEPPER_IP_ENV=192.168.31.30
set SUIYUE_CLOUD_WS=ws://192.168.31.10:8000/xiaozhi/v1
set PEPPER_PY2_EXE=C:\Python27\python.exe          :: ★显式指定，不依赖 PATH
set PEPPER_PY3_EXE=C:\Python313\python.exe
set PEPPER_INSTALL_DEPS=1

start_pepper_debug.bat
```

**脚本会自动做**：① 设 SDK 环境 → ② 校验 Py2.7 import → ③ 以 `--auto-bridge` 启动主网关
（自动拉起 Py2.7 桥子进程）。

| 可覆盖变量 | 默认值 |
|---|---|
| `PEPPER_SDK_ENV` | `%~dp0..\..\pynaoqi-python2.7-2.5.7.1-win32-vs2013` |
| `PEPPER_IP_ENV` | `pepper.local` |
| `SUIYUE_CLOUD_WS` | `ws://192.168.31.10:8000/xiaozhi/v1` |
| `PEPPER_PY2_EXE` | `python2.7` |
| `PEPPER_PY3_EXE` | `python` |
| `PEPPER_DEVICE_ID` | `pepper-01` |
| `PEPPER_INSTALL_DEPS` | 未设则跳过装依赖 |

**停止**：窗口内 `Ctrl+C`（脚本会先发 `stop_all` 再退出，桥子进程一并结束）。

### 8.3 内网代理（**本项目真实踩过的坑**）

```bat
set no_proxy=192.168.31.*,localhost,127.0.0.1
set NO_PROXY=192.168.31.*,localhost,127.0.0.1
```

> `websockets>=14` 的 `connect()` **默认读 `http_proxy`**。若这台机器设了代理
> （公司机常见），会连不上 4090。项目已在 chassis 侧用 `proxy=None` 兜底，
> 但网关侧建议也设上。

### 8.4 分层启动（调试时用）

```bat
:: 只起 Py2.7 桥 —— 验证协议层，不依赖云端
pepper_bridge.bat
::另开一个窗口，用 Py3 测试客户端连 127.0.0.1:9560
C:\Python313\python.exe suiyue\pepper\test_bridge_client.py

:: 只起 Py3 主网关 —— 需桥已在 :9560 监听
pepper_gateway.bat
```

> 💡 **分层排查的价值**：能快速区分"协议层/硬件层"与"云端层"的问题。

---

## 9. 部署后如何启动（完整顺序）

```bash
# === 4090 上（另开终端/SSH）===
sudo systemctl start ollama# 或在线API方案则跳过
sudo systemctl start xiaozhi-server
# 确认输出：Websocket地址是 ws://<4090_IP>:8000/xiaozhi/v1/

# === Pepper 网关机上 ===
1. ssh 到 Pepper，持久化关掉 boot-config（§8.1）
2. 启动脚本（§8.2）
3. 看日志，应见：
   - [bridge] connected to Pepper broker: tcp://<IP>:9559
   - [bridge] IPC listening on 127.0.0.1:9560
   - 已发送 hello 握手 -> ws://<4090_IP>:8000/xiaozhi/v1
   - emotion=xxx -> 岁悦 yyy -> actionzzz   （情绪契约生效）
```

---

## 10. 验收清单

### 装机

- [ ] `platform.architecture()` → `('32bit', 'Windows')`
- [ ] `C:\Python27\python.exe -c "import qi, naoqi"` → `sdk OK`
- [ ] `C:\Python313\python.exe -c "import websocket"` → `ws OK`
- [ ] `C:\Python313\python.exe -c "import opuslib; opuslib.Encoder(16000,1,'voip')"` → `opus OK`

### 连通

- [ ] `qi.Session().connect('tcp://<PEPPER_IP>:9559')` 成功，`services()` 非空
- [ ] `boot-config` 已持久关闭（重启验证过）
- [ ] 4090 的 WS 端口可达：`telnet <4090_IP> 8000`

### 联调（分层）

- [ ] L1 协议层：JSON 收发稳定
- [ ] L2 硬件层：emote / approach / stop_all 全部 `ok:true`
- [ ] L4 安全层：kill 主网关 →桥15s内自动 `stop_all`
- [ ] L6 端到端：说话 → Pepper 出声 + 做动作

---

## 11. 排障速查

| 现象 | 原因 | 处置 |
|---|---|---|
| `DLL load failed %1 不是有效的 Win32 应用程序` | 🔴 Py3 装成 64 位 | 重装 **x86** 版 Py3 |
| `ImportError: No module named qi` | `PYTHONPATH` 错 | 设 `%SDK%\lib` |
| `[WinError 126]` | `PATH` 缺 `%SDK%\bin` | 加上；仍不行再装 VC++ 2013 x86 |
| `could not load library 'libopus'` | 🔴 缺 32 位 libopus.dll | 见 §6.1 |
| 连不上 4090 的 WS | `http_proxy` 劫持 | 设 `no_proxy`（§8.3） |
| 连不上 Pepper :9559 | IP 错 / 跨网段 | 同网直连；查 IP |
| Pepper 开机报"连接服务器失败" | `boot-config` 向导 | §8.1 |
| 会话正常但 **Pepper 不动** | 🔴 情绪契约未生效（见 `部署手册-4090与Pepper联调.md` §4.3 G3） | 查日志 `emotion=xxx ->` 那行 |
| 声音无法上行 | opus 缺失 | §6.1 |

---

## 附：与 4090 服务器的分工（别搞混）

| | 4090 服务器 | Pepper 网关机 |
|---|---|---|
| 系统 | Ubuntu 22.04 | Windows 10/11 x64 |
| 跑什么 | xiaozhi-server + 大脑 MCP + LLM + ASR + TTS | naoqi_bridge + 主网关 |
| Python | 3.10 | **2.7(x86) + 3.13(x86)** |
| GPU | 需要 | 不需要 |
| Docker | 可用 | **不需要** |
| 网络角色 | WS 服务端 :8000 | WS 客户端 + broker 客户端 :9559 |

> 📌 **一句话**：4090 是"大脑"，网关机是"手脚"。