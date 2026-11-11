# 4090 + Pepper 网关 部署与真机联调手册

> **适用场景**：明天上机，一次性完成「4090 对话引擎服务器部署」+「Pepper 网关部署」+「真机联调」。
>
> **已确认的部署形态**（2026-10-12，用户确认）：
> | 项 | 设定 |
> |---|---|
> | 4090 服务器 | **Ubuntu 22.04 LTS**，NVIDIA 驱动 + CUDA，与机器人同一局域网 |
> | Pepper 网关机 | **Windows x86 实体机**（32 位 Python 2.7 跑naoqi_bridge + Python 3.13 跑主网关） |
> | 网络 | 三者**同一局域网、平级直连**（4090 / 网关机 / Pepper 本体） |
> | 对话引擎分机 | **每本体一台 xiaozhi-server**（G4 决策）→ 本次只部署 Pepper 这一台 |
>
> **配套文档**（本手册不重复其内容）：
> `docs/DEPLOY-4090.md`（部署动作清单）· `docs/OFFLINE-MATERIALS.md`（离线物料 11 节）·
> `docs/OFFLINE-CHECKLIST.md`（逐项验收）· `pepper/真机联调checklist.md`（NAOqi 侧逐项验证）·
> `brain/mcp/XIAOZHI_SERVER_PATCHES.md`（overlay 台账）· `docs/adr/ADR-011`（离线基线）
>
> **核心原则**：**源码与部署物分离**。`xiaozhi-esp32-server` 部署在 4090 的
> `/opt/` 下，**不进 `suiyue/` 仓库**（会被 git 收编）。

---

## 阶段 0 · 今晚必做（不开机也能完成，且有不可逆项）

> ⚠️ **为什么必须今晚做**：ADR-011 决策 4 第 5 项明说——模型权重/ Docker 镜像
> 必须在**有网时**备齐，air-gapped 后补不回来。其余阶段都能明天做，**只有这一段不能**。

### 0.1 网络与地址规划（先定这个，后面全靠它）

| 设备 | 建议地址 | 端口 | 用途 |
|---|---|---|---|
| 4090 服务器 | `192.168.31.10` | 8000 / 8003 | xiaozhi WS / OTA |
| Pepper 网关机 | `192.168.31.20` | 9560 | naoqi_bridge IPC（**仅本机**，勿外暴露） |
| Pepper 机器人 | `192.168.31.30`（以实际为准） | 9559 | NAOqi broker |
| 大亮底盘（本期不接） | `192.168.31.7` | 6060 | chassis WS |

- [ ] 确认 4090 的实际 IP；与 `pepper/gateway_config.py:12` 的默认
      `SUIYUE_CLOUD_WS=ws://192.168.31.10:8000/xiaozhi/v1` 对齐
      （不一致则明天改，或用环境变量覆盖，**不要改代码默认值**）
- [ ] 路由器做 **IP 静态绑定**（DHCP 保留），避免重启后 IP 漂移
- [ ] 记录 Pepper 实际 IP（机器人设置→网络，或路由器 DHCP 列表）

> ⚠️ **内网代理坑（本项目踩过）**：部署机若设了 `http_proxy`，`websockets>=14`
> 的 `connect()` **默认读 `http_proxy`**，会导致连内网 WS 失败。
> 代码侧已用 `proxy=None` 兜底（`daliang_gateway/client.py`），但 Pepper 网关的
> WS 客户端与 server 侧仍需检查。见阶段 2 的 `no_proxy` 设置。

### 0.2 离线物料备齐（**不可逆，必做**）

逐条见 `docs/OFFLINE-MATERIALS.md`，最小集：

- [ ] **Qwen3-8B Q4**（Ollama）—— `ollama pull qwen3:8b`；air-gapped 导入用
      `Modelfile` + `FROM ./xxx.gguf`，**禁止 transformers FP16 加载**（16GB 会撑爆 24GB 卡）
- [ ] **SenseVoiceSmall**（ASR）→ 部署到 `models/SenseVoiceSmall/`
- [ ] **SileroVAD** → `models/snakers4_silero-vad/`（**注意上游拼写是 `snakers4`**）
- [ ] **GPT-SoVITS V3 权重 + 老人温和女声音色参考音频**
      ⚠️ 默认 `refer_wav_path: caixukun.wav`(L956) 是上游示例音频，**必须换掉**
- [ ] **Docker 镜像 tar**（若用 docker：`docker save` 成 tar）
- [ ] **Linux 对应版本的 wheels**（`pip download` 必须在 Linux 上做，Windows 下的 wheel 不通用）

### 0.3 Windows 网关机准备

- [ ] 确认网关机是 **32 位**：`python2.7 -c "import platform; print(platform.architecture())"`
      预期 `('32bit', 'Windows')`。**ARM/树莓派不可用**（SDK 是 32 位）
- [ ] 装 **Python 2.7.18**（最后一个 2.7 版）
- [ ] 确认 pynaoqi SDK 在位：`D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013\`
      （已核实 `lib/` 与 `bin/` 均存在）
- [ ] 装 **Python 3.13**（跑主网关），并 `pip install -r suiyue\pepper\requirements.txt`
- [ ] 把明天要用的文件准备好：`suiiyue\` 整个目录 + SDK 目录（**不要拷来拷去**，直接在这台机上操作）

---

## 阶段 1 · 4090 基础环境（明天上午，约 1–2 小时）

### 1.1 系统与驱动

```bash
# --- 系统信息 ---
uname -a                    # 期望 Linux ... 5.15.0-xx-generic (Ubuntu 22.04)
lsb_release -a

# --- GPU 与驱动 ---
nvidia-smi                  # 关键：确认 4090 在位、驱动正常、CUDA 版本
                            # 期望：NVIDIA-SMI xxx.xx + "CUDA Version: 12.x"
# --- 显存 ---
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
                            # 期望：NVIDIA GeForce RTX 4090, 24576 MiB

# --- 资源 ---
free -h                     # 建议 ≥ 16GB（ADR-011 说对话引擎 2-4GB，但要给 Ollama/TTS 留余量）
df -h /                     # 建议 ≥ 100GB（权重 + Docker 镜像很占）
lscpu | grep -E "Model name|CPU\(s\)"
```

- [ ] 记录以上输出到 `brain/mcp/XIAOZHI_SERVER_PATCHES.md` §1 台账备注

> ⚠️ 如果 `nvidia-smi` 不认卡，先装驱动（`sudo ubuntu-drivers autoinstall`），
> **不要急着装 CUDA Toolkit** —— 驱动自带 CUDA runtime，PyTorch 用 pip 版即可。

### 1.2 基础软件

```bash
# --- 系统更新 ---
sudo apt update && sudo apt -y upgrade

# --- 必备工具 ---
sudo apt -y install \
  python3.10 python3.10-venv python3-pip \
  git wget curl unzip \
  build-essential cmake \
  ffmpeg sox libsox-dev       # 音频处理，GPT-SoVITS / 音频转码需要
  libopus0                    # ⚠️ 若网关机用 opus 编解码则相关；server 侧一般不需要

# --- Docker（若用容器部署 server） ---
sudo apt -y install docker.io docker-compose-v2
sudo systemctl enable --now docker
sudo usermod -aG docker $USER   # 需重新登录生效
docker --version && docker compose version

# --- 防火墙（本项目自建，建议开） ---
sudo ufw allow 22/tcp         # SSH
sudo ufw allow 8000/tcp       # xiaozhi WS
sudo ufw allow 8003/tcp       # OTA
sudo ufw enable
```

- [ ] 验证：`python3 --version` 应为 3.10.x；`docker --version` 有输出

### 1.3 Ollama（LLM 后端）

```bash
curl -fsSL https://ollama.com/install.sh | sh
# 离线环境下改为：先在有网机装好，再 `scp` 二进制 + 模型目录过来

sudo systemctl enable ollama
# systemd 服务必须加模型存储路径环境变量，否则找不到离线模型
sudo systemctl edit ollama
# 写入：
#   [Service]
#   Environment="OLLAMA_MODELS=/opt/models/ollama"
sudo systemctl daemon-reload && sudo systemctl restart ollama

ollama pull qwen3:8b            # 有网时；离线见 0.2
ollama list                      # 确认 qwen3:8b 在列
curl -s http://127.0.0.1:11434/api/tags   # API 探活
```

- [ ] **显存实测**：`nvidia-smi` 应看到 Ollama 占用 5–6GB（8B Q4）
- [ ] 简单对话验证：`ollama run qwen3:8b "你好，请只回答：岁悦已就位"`

### 1.4 GPT-SoVITS（TTS 后端）★ 头号必改项

```bash
cd /opt
git clone https://github.com/RVC-Boss/GPT-SoVITS.git
cd GPT-SoVITS
bash install.sh              # ⚠️ 会创建独立环境并装 torch，注意版本
# 拉取 V3 权重 + 老人音色模型（离线需提前下好）
bash download_models.sh
```

> ⚠️ **torch 版本冲突风险**：`GPT-SoVITS` 依赖的 torch 版本可能与 server 的
> `torch==2.2.2` 不兼容。**建议 TTS 独立进程/独立虚拟环境**，不要与 server 混装。

- [ ] 启动：`bash api_v2.py`（默认 `http://127.0.0.1:9880`）
- [ ] 探活：`curl -s http://127.0.0.1:9880/health`
- [ ] 用老人音色试合成一句，确认 `refer_wav_path` 已换成你的音频

---

## 阶段 2 · 部署 xiaozhi-server + 岁悦大脑（下午，约 2–3 小时）

### 2.1 放置代码（源码与部署物分离）

```bash
# --- server（部署物，不进 git 仓库）---
sudo mkdir -p /opt/xiaozhi-esp32-server
cd /opt
sudo wget https://github.com/xinnan-tech/xiaozhi-esp32-server/archive/refs/tags/v0.9.7.zip
sudo unzip -q v0.9.7.zip
sudo cp -r xiaozhi-esp32-server-0.9.7/* /opt/xiaozhi-esp32-server/
sudo rm -r xiaozhi-esp32-server-0.9.7 v0.9.7.zip
# 部署后立刻把版本号记进 suiyue/brain/mcp/XIAOZHI_SERVER_PATCHES.md §1 台账

# --- 岁悦大脑（源码，应入 git）---
sudo mkdir -p /opt/suiyue
# 从 Windows 同步（保持 git 仓库完整，历史可追溯）
# Windows 侧执行：
#   scp -r "D:\WorkBuddy\桌面陪伴机器人\suiyue" user@4090:/opt/
```

- [ ] 核对 server 结构：`python3 suiyue/tools/inspect_xiaozhi_server.py /opt/xiaozhi-esp32-server`
      期望结构完整 + 输出 X1/X2/X3 落点行号

### 2.2 Python 环境与依赖

```bash
cd /opt/xiaozhi-esp32-server/main/xiaozhi-server
python3.10 -m venv /opt/venvs/xiaozhi-server
source /opt/venvs/xiaozhi-server/bin/activate
pip install -r requirements.txt
# ⚠️ requirements.txt 含 torch==2.2.2 / funasr==1.2.7 / modelscope==1.39.1 等，
#    首次安装耗时长（30-60 min）。若 GPU 版 torch 需按 CUDA 版本指定 index

# 放置离线模型（阶段 0.2 备好的）
mkdir -p models
cp -r /tmp/offline/SenseVoiceSmall models/
cp -r /tmp/offline/snakers4_silero-vad models/
```

### 2.3 **先跑通原版（关键纪律）**

> ⚠️ **不要一上来就改 overlay**。先确认原版能起来，否则出问题时分不清是
> 上游环境问题还是我们的改动引入的。

```bash
cd /opt/xiaozhi-esp32-server/main/xiaozhi-server
source /opt/venvs/xiaozhi-server/bin/activate
python3 app.py            # 或按上游 README 的 docker compose 方式
```

- [ ] server 起来无 config 解析错误
- [ ] 日志能看到 WS 服务监听 8000
- [ ] **记录启动方式到 PATCHES 台账备注**（明天复现要用）

### 2.4 改配置为全离线（ADR-011 决策 4）

编辑 `/opt/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml`：

| 配置项 | 行号 | 改成 |
|---|---|---|
| `selected_module.TTS` | L243 | `GPT_SOVITS_V3`（默认 `EdgeTTS` **走微软服务器，联网**） |
| `selected_module.LLM` | L239 | `OllamaLLM`（上游已内置 L664，只改名字） |
| `selected_module.ASR` | L237 | `FunASR` 不变（本地已满足） |
| `selected_module.VAD` | L235 | `SileroVAD` 不变 |
| `selected_module.Intent` | L251 | `function_call` 不变 |
| `TTS.GPT_SOVITS_V3.refer_wav_path` | L956 | **换成老人温和女声音色** |
| `Intent.function_call.functions` | L280 | **禁用联网项**：`web_search` / `get_weather` / `get_news_from_newsnow` |

- [ ] 改完确认 `python3 -c "import yaml;yaml.safe_load(open('config.yaml',encoding='utf-8'))"` 不报错

### 2.5 放置 overlay（3 处薄改动）

> ⚠️ **两个脚本各管一半，`suiyue_scene.py` 必须手动拷** ——
> `apply_overlay_x1x2.py` 只改 `config.yaml` + `mcp_server_settings.json`；
> `apply_overlay_x3.py` **只改 `connection.py`，不拷贝注入器**。
> 漏拷这步 → server起不来（`import suiyue_scene` 失败虽有 try/except 兜底，
> 但**场景包永远不会被注入**，表现为"overlay 好像没生效"且无明显报错）。

```bash
# 步骤 1：先拷注入器（含 1.3 情绪表达增强，务必用最新版）
cp /opt/suiyue/overlay/suiyue_scene.py \
   /opt/xiaozhi-esp32-server/main/xiaozhi-server/core/suiyue_scene.py

# 步骤 2：跑幂等脚本改另外两处（自带备份 *.suiyue.bak，可回滚）
cd /opt/suiyue
python3 tools/apply_overlay_x1x2.py /opt/xiaozhi-esp32-server
python3 tools/apply_overlay_x3.py  /opt/xiaozhi-esp32-server

# 步骤 3：验证三处都在位
grep -n "suiyue" /opt/xiaozhi-esp32-server/main/xiaozhi-server/config.yaml | head -3
grep -n "suiyue-brain" /opt/xiaozhi-esp32-server/main/xiaozhi-server/mcp_server_settings.json
grep -n "suiyue_scene" /opt/xiaozhi-esp32-server/main/xiaozhi-server/core/connection.py
ls -l /opt/xiaozhi-esp32-server/main/xiaozhi-server/core/suiyue_scene.py
```

- **X1** `config.yaml` 加 `suiyue.device_id: pepper-01`（**必须与大脑 `config.yaml` 字面一致**）
- **X2** `mcp_server_settings.json` 注册 `suiyue-brain`（stdio；注意 `args` 里
      `brain_repo` 要改成 4090 上的 `/opt/suiyue`）
- **X3** `connection.py` `_init_prompt_enhancement()` 注入场景包（改 2 处约 8 行）

> ⚠️ **X2 的 `args` 是最易错的**：示例里 `brain_repo` 可能是 Windows 路径，
> 必须改成 `/opt/suiyue`，且 `command` 要用部署机上的 `python3`绝对路径
> （venv 内的是 `/opt/venvs/xiaozhi-server/bin/python3`）。
> 建议直接写绝对路径，避免 stdio 子进程因PATH 找不到解释器而静默启动失败。

---

### 2.5.1 Windows 网关机的 32 位依赖坑（**已实测 SDK 内容修正**）

> ⚠️ 以下结论于 2026-10-12 **实测 `pynaoqi` SDK 目录后修正**，比原判断更准确。

| 坑 | 实测结论 | 处置 |
|---|---|---|
| **VC120 运行库** | ✅ **不用装**。实测 SDK 的 `bin/` 与 `lib/` **自带** `msvcr120.dll` / `msvcp120.dll`（另有 `libeay32.dll` / `ssleay32.dll` 即OpenSSL） | 只要 `PATH` 含 `%SDK%\bin` 即可；若仍报 `[WinError 126]` 再补装 VC++ 2013 x86 |
| **opus 编解码** | 🔴 **必须装 opuslib，无法绕过**。核实 `xiaozhi-server/core/connection.py:119`：`self.audio_format = "opus"` **全文件仅此一处、不接受 hello 协商** → **设 `PEPPER_AUDIO_FORMAT=raw` 会导致音频链路失败** | 在 32 位 Python 下 `pip install opuslib`（纯 ctypes 包装）+ 放 32 位 `libopus.dll` 到 PATH。**若装不上→ 音频无法上行**，此时可临时设 raw 验证"能否握手成功"，但**语音功能不可用** |
| **Py3 必须 32 位** | `pynaoqi` 决定了整台机是 32 位 | 主网关的 Py3 也用 32 位；`websocket-client` 是纯 Python，**无 ABI 问题** |
| **Py2.7 与 Py3 共存** | 两个解释器 PATH 顺序易乱 | `--auto-bridge` 用 `PEPPER_PY2_EXE` **显式指定绝对路径**，不依赖 PATH 顺序 |

- [ ] **明天第一件事**：装完依赖立刻测三件事
      ```bat
      python -c "import websocket; print('ws ok')"
      python -c "import opuslib; print('opuslib ok')"   :: 不行则音频链路起不来
      python2.7 -c "import qi, naoqi; print('sdk ok')"
      ```

> **X3 性能关键**：首次 stdio 调大脑 MCP 约 **13 秒**（拉子进程 + 加载场景包）。
> **务必在 server 启动处加后台预热**，否则首个会话会卡 13 秒：
> ```python
> import threading
> from core.suiyue_scene import warmup
> threading.Thread(target=warmup, args=(config,), daemon=True).start()
> ```

### 2.6 接大脑 MCP server

- [ ] 用 `brain/mcp/xiaozhi-mcp-settings.example.json` 注册大脑 MCP（stdio 拉起）
- [ ] 在 4090 上单独验证大脑侧可独立跑：
      ```bash
      cd /opt/suiyue && python3 -m brain.mcp --config brain/mcp/config.yaml
      ```
- [ ] 验证工具暴露门禁（**必须 exit 0**）：
      ```bash
      cd /opt/suiyue && python3 tools/precheck_brain_mcp.py
      ```
      期望：`PASS: 下发给 LLM 的工具全部已注册` + `可安全执行 overlay X1/X2/X3`

---

## 阶段 3 · Pepper 网关部署（Windows 机，约 1 小时）

> ⚠️ **架构分工**（ADR-011 决策 3）：Pepper 网关是**纯客户端**，
> 不跑任何 AI 模型。它只做两件事——麦克风/扬声器 I/O + NAOqi 动作派发。

### 3.1 环境准备

```bat
:: 1) 确认 32 位 Python 2.7（pynaoqi SDK 是 32 位）
python2.7 -c "import platform; print(platform.architecture())"
:: 预期：('32bit', 'Windows')

:: 2) 验证 pynaoqi 可 import
set SDK=D:\WorkBuddy\桌面陪伴机器人\pynaoqi-python2.7-2.5.7.1-win32-vs2013
set PYTHONPATH=%SDK%\lib
set PATH=%SDK%\bin;%SDK%\lib;%PATH%
python2.7 -c "import qi, naoqi; print('qi+naoqi import OK')"
:: 预期：qi+naoqi import OK
```

- 失败排查：`ImportError: No module named qi` → PYTHONPATH 错；
  `[WinError 126]` → PATH 未加 `%SDK%\bin`（**VC120** 运行库问题）

### 3.2 broker 连通性验证（**联调第一道门**）

> 🔴 **开机前必做**：先按§3.2.1 关掉 `boot-config`（getting started wizard），
> 否则每次开机都会弹"连接服务器失败"，且部分功能被阻塞。

```bat
python2.7 -c "import qi; s=qi.Session(); s.connect('tcp://<PEPPER_IP>:9559'); print('connected, services=', len(s.services()))"
:: 预期：connected, services= <正整数>
```

- `ConnectionRefused` → Pepper 未上电 / IP 错 / 端口非 9559
- `timeout` → 跨网段隔离，改为同网直连（文档实证 `--qi-url` 直连**无需开发者模式**）

---

### 3.2.1 关闭 boot-config（getting started wizard）★ 新增，必做

**现象**（用户 2026-10-12 报告）：Pepper 开机时提示**连接服务器失败**；
ssh 进去 `stopBehavior boot-config` 后，**本地内网使用一切正常**。

**这是什么**：`boot-config` 是 NAOqi 的 **Getting Started Wizard**（首次使用向导，
由 `ALBehaviorManager` 管理）。向导里有一步要求连接
**Aldebaran 社区账号**并做应用更新/系统升级——air-gapped 下必然失败并反复重试，
**且部分功能被阻塞**。它不是 NAOqi 启动必需项，关掉完全不影响 `qi.Session` 通信与
我们自己的 `naoqi_bridge`。

**⚠️ 与文档既有结论的差异**：`OFFLINE-CHECKLIST.md` 原记"Pepper 开机无需联网激活
（已确认）→ air-gapped 前置条件满足"。实测表明 **"免激活"成立，但"免联网"不成立**——
开机仍会主动外连并报错。**这不阻断部署，但必须显式关掉，否则每次开机都要 ssh 干预。**

#### 一次性关闭（明天做）

```bash
# ssh 到 Pepper（默认 nao / nao 用户）
ssh nao@<PEPPER_IP>

# 1) 查状态（确认真在跑）
qicli call ALBehaviorManager.isBehaviorRunning boot-config

# 2) 停止（立即生效，但重启后会再起来 —— 见下方持久化）
qicli call ALBehaviorManager.stopBehavior boot-config
```

#### 持久化（**推荐，否则每次重启都要重来**）

`ALBehaviorManager` 有一组 *default behavior* 机制：被标为 default 的 behavior
在 **NAOqi 启动时自动运行**。`boot-config` 就是其中之一。移除它：

```bash
# 3) 从 default 列表移除 -> 开机不再自动启动
qicli call ALBehaviorManager.removeDefaultBehavior boot-config

# 4) 验证：应输出不含 boot-config
qicli call ALBehaviorManager.getDefaultBehaviors
```

#### 验收（**必须做，否则不算修好**）

- [ ] 重启 Pepper（`sudo reboot` 或长按胸章按钮关机再开机）
- [ ] **确认开机不再弹"连接服务器失败"**
- [ ] `qicli call ALBehaviorManager.isBehaviorRunning boot-config` → `False`
- [ ] `qicli call ALBehaviorManager.getDefaultBehaviors` 输出里**无** `boot-config`
- [ ] broker 仍可连：`qicli --qi-url tcp://127.0.0.1:9559 list`

#### 如果 `removeDefaultBehavior` 不生效（版本差异兜底）

2.5.x 上 `boot-config` 可能由**应用包的 manifest 自动启动**标志控制，可试：

```bash
# 找出声明了 autorun / default 的包
grep -rl "boot-config" ~/.local/share/PackageManager/apps/ 2>/dev/null
# 编辑对应包的 manifest.xml，把 autorun 改为 false，然后重启 PackageManager 服务
sudo systemctl restart naoqi 2>/dev/null || sudo reboot
```

> ⚠️ **不要动** `/etc/naoqi/autoload.ini`（那是系统模块清单，只有 root 能改），
> 也不要卸载 NAOqi 核心模块。`boot-config` 是"应用层"的可关闭项。

#### 顺带建议关掉的同类项（可选，air-gapped 优化）

```bash
# 自主行为（否则会抢我们 EMOTION_TO_ACTION 的控制权）—— 联调纪律要求
qicli call ALAutonomousLife.setState disabled

# 内置云端服务（改走我们的云端链路，见 ADR-011 决策 4 第 8 项）
# ⚠️ 只在确认不再需要内置语音时执行；执行前先跑一遍 §4 分层联调确认新链路通
```

| 失败现象 | 原因 | 处置 |
|---|---|---|
| `isBehaviorRunning` 返回 True 但关不掉 | 向导持有独占资源/正在等待网络 | 先断网再 `stopBehavior` |
| `removeDefaultBehavior` 报找不到 behavior | 版本差异，名字带包前缀 | 用 `getInstalledBehaviors` 查全名（可能是 `<pkg>/boot-config`） |
| 重启后又出现 | 只做了 stop 没做 removeDefault | 必须执行第 3 步持久化 |

### 3.3 一键启动（推荐）

```bat
:: 在 suiyue\pepper\ 目录下执行；默认参数可用环境变量覆盖
set PEPPER_IP_ENV=192.168.31.30
set SUIYUE_CLOUD_WS=ws://192.168.31.10:8000/xiaozhi/v1
set PEPPER_INSTALL_DEPS=1
start_pepper_debug.bat
```

脚本会：① 设 SDK 环境 → ② 校验 Py2.7 import → ③ 以 `--auto-bridge` 启动主网关
（自动拉起 Py2.7 桥子进程）。

- **停止**：窗口内 `Ctrl+C`（先发 `stop_all` 再退出，桥子进程一并结束）
- 可用覆盖变量：`PEPPER_SDK_ENV` / `PEPPER_IP_ENV` / `SUIYUE_CLOUD_WS` /
  `PEPPER_PY2_EXE` / `PEPPER_PY3_EXE` / `PEPPER_DEVICE_ID` / `PEPPER_INSTALL_DEPS=1`

### 3.4 关键内网设置（**踩过坑**）

```bat
:: 内网 WS 必须绕过代理，否则连不上 4090
set no_proxy=192.168.31.*,localhost,127.0.0.1
set NO_PROXY=192.168.31.*,localhost,127.0.0.1
```

> `websockets>=14` 的 `connect()` **默认读 `http_proxy` / `no_proxy`**。
> 本项目已在 chassis 侧用 `proxy=None` 显式兜底，但网关机与 server 侧
> 仍建议设 `no_proxy`——**这是本项目真实踩过的坑**，不是理论风险。

---

## 阶段 4 · 真机联调（联调执行主体）

> **详细逐项验证见 `pepper/真机联调checklist.md`**（§0–§10，含 PASS 判据与失败排查）。
> 本节只给**执行顺序与阶段目标**，避免与那份文档重复。

### 4.1 联调前安全检查（**必做，不可跳过**）

- [ ] Pepper 周围 **1.5m 净空**，人员退至侧后
- [ ] **物理急停按钮**（后颈/底座）在伸手可及范围
- [ ] Pepper 立于平整无障碍区
- [ ] **先验证 `stop_all` 急停可用**，再跑任何动作
- [ ] `approach` / `navigate` 距离从 **0.3m 小步进**起
- [ ] 联调期**禁用** `ALAutonomousLife`（避免 NAOqi 自主行为抢控制权）：
      `session.service("ALAutonomousLife").setState("disabled")`
- [ ] **不实例化** `ALSpeechRecognition` / `ALTextToSpeech` / `ALDialog`（改云端）

### 4.2 分层联调（按此顺序，每层独立定位问题）

| 层 | 做什么 | 对应 checklist | 判据 |
|---|---|---|---|
| **L1 协议层** | 只起 Py2.7 桥，用 `test_bridge_client.py` 连 127.0.0.1:9560 | §6 第一步 | JSON 行收发稳定、音频帧连续 |
| **L2 硬件层** | 动作原语冒烟：emote / approach / tablet_render / get_status / stop_all | §5 | 全部 `ok:true` |
| **L3 音频层** | 麦克风上行 + 扬声器下行 | §4 / §9 G8 | 能收帧、能出声 |
| **L4 安全层** | 失联看门狗：kill 主网关 → 桥应在 15s 内自动 `stop_all` | §7 | 日志出现 `[watchdog] 主网关心跳超时` |
| **L5 云端层** | 主网关连 4090 的 xiaozhi WS，跑通对话 | §8 G4 | server 能连上、能收音 |
| **L6 端到端** | 说一句话 → Pepper 回应 + 做动作 | §8 G3/G4 | **情绪动作对应正确** |

> **为什么分层**：L1/L2 不需要云端，能把"协议问题"和"硬件问题"和
> "云端问题"彻底解耦。否则出问题时会互相怀疑，浪费大量时间。

### 4.3 本次重点验证的三个跨组件契约（易静默失败）

| 项 | 风险 | 怎么验 |
|---|---|---|
| **G3** emotion | 🔴 **双重依赖**：① 云端 21 标签 ↔ 岁悦 6 键**已修**（翻译层 `SERVER_EMOTION_TO_SUYUE`）；② 但云端 `get_emotion()` **靠扫描 LLM 回复里的第一个 emoji** 判定情绪 → **LLM 不吐 emoji 就恒 `neutral` → Pepper 恒静默不动**。② 靠 1.3 增强（场景包 `expression` 段 + X3 注入 prompt）解决，**必须确认 X3 真的注入了「【情绪表达】」段** | 看日志是否打出 `emotion=xxx -> 岁悦 yyy -> action`（`gateway.py`）。<br>另查 server 侧 prompt 日志里**是否有「【情绪表达】」条目** |
| **G4** 设备绑定 | MCP 返回成功 ≠ 本体有反应 | 触发 `self.suiyue.emote(device_id="pepper-01")`，**两条都要**：①工具返回成功 ②Pepper 真动了 |
| **G7** 动画标签 | 写错动画名 → `play` 返回成功但**不动**（静默） | 先 `getAnimationNames()` 列出真机可用动画，再回填 `EMOTION_TO_ACTION` |

> 🔴 **G3 是本次最容易"看起来正常但其实全错"的点**。
> 典型症状：对话能进行、动作也在做，但**Pepper 永远只是 Stand**，
> 日志里只有 `emotion=happy -> 岁悦 neutral -> posture Stand` 这类行。
> 排查顺序：① prompt 里有「【情绪表达】」吗 → ② LLM 真的吐 emoji 了吗
> → ③ 日志里翻译是否命中 → ④ 动画名在真机存在吗（见 G7）。

### 4.4 真机实测必回填的项（否则下次还得重测）

- [ ] 真机可用动画名 → `gateway_config.py` `EMOTION_TO_ACTION` + `pepper_cn_v1` 场景包
- [ ] 音频回调签名 / 事件名 / 每帧样本数 → `naoqi_bridge/audio.py`
- [ ] 扬声器通道号 → `audio.py:play_audio()`
- [ ] 巡游点位与禁区坐标 → `mobility.yaml` / `safety.yaml`（需 ALNavigation 建图）
- [ ] checklist §8/§9 每项实测结论 → `naoqi_bridge/README.md` 的 TODO 清单

---

## 阶段 5 · 验收（收尾）

### 5.1 对话引擎侧（不依赖真机也可查）

- [ ] server 起得来、config 无解析错（X1 生效）
- [ ] 启动日志见 MCP client 连上大脑（X2 生效）
- [ ] 会话日志见 `get_scene` 被调、`scene_pack=pepper_cn_v1`（X3 生效）
- [ ] **断大脑 MCP → 会话仍能开**（回退原始 prompt，不崩）
- [ ] LLM 实际收到的 system prompt 含 persona 语气 + safety 硬规则
- [ ] `precheck_brain_mcp.py` exit 0

### 5.2 离线验收（ADR-011 决策 4）

- [ ] 走一遍 `docs/OFFLINE-CHECKLIST.md`
- [ ] **断网测试**（最有效的一招）：把 4090 默认网关指向黑洞/防火墙阻断出站
      → 跑一轮完整对话 → **日志里所有超时的请求就是漏网的联网点**
      （比逐条排查快得多）

### 5.3 端到端体验验收

- [ ] `e2e` 的 5 项指标人工复核：语音出声 ≤1.5s / 动作起始 ≤2.5s / 三设备同步 ≤300ms
- [ ] 连续运行 4h 无崩溃
- [ ] 断网 30s 内自恢复

---

## 回滚预案

| 风险 | 触发信号 | 回滚动作 |
|---|---|---|
| overlay 改坏 server | 起不来 / config 解析错 | `cp *.suiyue.bak` 覆盖（脚本自动备份） |
| server 升级后失效 | 升级后行为异常 | 按 `XIAOZHI_SERVER_PATCHES.md` §3 逐条重做 3 处 |
| 大模型 OOM | `nvidia-smi` 显存爆 | 换更小量化（14B→8B）；**禁用 FP16** |
| Pepper 失控 | 动作用�� | **物理急停按钮**（软件不可靠时唯一手段） |
| 网关失联 | Pepper 状态异常 | 桥侧看门狗 15s 自动 `stop_all`（联调时必须验证过） |
| 底盘失联（本期不接） | — | ADR-011 决策 3：`softScram` |

---

## 明天的时间分配建议

| 时段 | 内容 | 预估 |
|---|---|---|
| 上午 | 阶段 1（4090 环境 + Ollama + GPT-SoVITS） | 2–3h |
| 下午 | 阶段 2（server 部署 + overlay + 接大脑） | 2–3h |
| 傍晚 | 阶段 3 + 4（Pepper 网关 + 分层联调） | 2–3h |
| 收尾 | 阶段 5（验收 + 回填实测结论） | 1h |

> **优先级提示**：若时间不够，**保住阶段 0 的物料 + 阶段 1 的 Ollama**
> （这两项是 air-gapped 后不可逆的），其余可延后。