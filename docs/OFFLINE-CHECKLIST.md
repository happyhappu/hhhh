# 岁悦 · 全离线部署 Checklist（air-gapped）

> 配套 `adr/ADR-011-全离线部署基线.md`
> 使用方式：**按顺序打勾，任一未勾都不能宣称"可离线"**。
> 断网后补任何一项都要重做阶段 4 的验收。

---

## 阶段 0 · 有网时准备（**不可跳过，离线后无法补**）

算力基线：单台 4090（24GB）。预算见 ADR-011 §决策 2。

- [ ] **0.1** 创建权重目录 `models/`，下载 ASR 权重
  - [ ] FunASR `SenseVoiceSmall/model.pt`（ModelScope，`~900MB–1.5GB`）
- [ ] **0.2** 拉取 LLM：`ollama pull qwen3:8b`（Q4_K_M ≈ 5GB）
  - [ ] 备选高价值模型：`ollama pull qwen3:14b`（Q4 ≈ 9GB，按需加载）
  - [ ] 确认 **不是** FP16 加载（8B FP16 = 16GB，单卡必爆）
- [ ] **0.3** TTS 权重与参考音频
  - [ ] GPT-SoVITS V3（或 Index-TTS / FishSpeech）权重下载完成
  - [ ] 老人音色参考音频 ≥ 2 段（5–10s 干净人声），已试听确认自然
- [ ] **0.4** Embedding：`bge-small-zh-v1.5`（可 CPU）
- [ ] **0.5** Docker 镜像离线化（若走容器）
  - [ ] `docker pull ghcr.io/xinnan-tech/xiaozhi-esp32-server:server_latest`
  - [ ] `docker save -o xiaozhi-server.tar <image>` → 拷贝到目标机 → `docker load -i`
  - [ ] 一并 save：redis（若用）、tts 服务镜像
- [ ] **0.6** Python 轮子离线化（若走源码部署）
  - [ ] `pip download -r requirements.txt -d wheels/` 在有网机执行，目标机 `pip install --no-index --find-links=wheels/`
- [ ] **0.7** 拷贝 `suiyue/` 仓库到目标机（git bundle 或 U 盘）

> 提示：0.5 / 0.6 二选一即可，**不要混合**——混合部署最容易出现"容器里缺一个本地 pip 包"。

---

## 阶段 1 · 服务器底座

- [ ] **1.1** NVIDIA 驱动 + CUDA 就绪，`nvidia-smi` 能看见 24GB
- [ ] **1.2** Ollama 启动并常驻：`ollama serve`，`curl http://127.0.0.1:11434/api/tags` 有 qwen3:8b
- [ ] **1.3** 设置显存上限，避免与其他服务互抢
  - [ ] Ollama：按需设 `OLLAMA_MAX_LOADED_MODELS=2`、`OLLAMA_KEEP_ALIVE`
  - [ ] 若用 vLLM：显式 `--gpu-memory-utilization 0.45`（给 ASR/TTS 留位）
- [ ] **1.4** 静态内网 IP（如 `192.168.31.10`），或在路由器做 DHCP 静态绑定
- [ ] **1.5** NTP 服务端就绪
  - [ ] Windows：`w32tm /config /reliable:yes /manualpeerlist:127.0.0.1 /syncfromflags:manual` → 或直接让服务器自身时钟可信
  - [ ] Linux：`chrony` 允许内网段 `allow 192.168.31.0/24`
  - [ ] 路由器 DHCP option 42 指向该 IP（**否则 ESP32 重启后时间归零**）
- [ ] **1.6** 防火墙：放行 8000（WS）、8003（OTA）、11434（Ollama）、TTS 服务端口，**仅限内网段**

---

## 阶段 2 · 小智云端本地化

先确认本机有哪些后端实现（键名以实际版本为准，别照抄）：

```bash
ls main/xiaozhi-server/core/providers/tts/      # 看有哪些 TTS 实现
ls main/xiaozhi-server/core/providers/asr/
grep -n "selected_module" -A 12 data/.config.yaml
```

- [ ] **2.1** 部署形态 = **server-only**（`.config.yaml` 文件配置，无数据库）
- [ ] **2.2** `selected_module` 全部指向本地后端：

```yaml
server:
  websocket: ws://192.168.31.10:8000   # 内网 IP，非 localhost
  ota: http://192.168.31.10:8003/xiaozhi/ota/
selected_module:
  VAD: SileroVAD
  ASR: FunASR
  LLM: OllamaLLM          # 键名以实际版本 config.yaml 为准
  TTS: GPT_SOVITS_V3      # ← 绝不能是 EdgeTTS
  Intent: function_call
  Memory: mem_local_short
  VLLM: ~                 # 本期不用，置空
LLM:
  OllamaLLM:
    base_url: http://127.0.0.1:11434
    model_name: qwen3:8b
```

- [ ] **2.3** 全文搜索配置文件，确认**没有任何 API Key 残留**
  - [ ] `grep -rniE "sk-|api_key|https?://(?!192\.168|127\.)" data/.config.yaml`
- [ ] **2.4** 插件清理（联网插件是第二大坑）
  - [ ] 天气 / 新闻 / 音乐 / 搜索类插件：禁用 或 改为本地 mock
  - [ ] 老人高频问天气 → 必须有降级话术（"我没联网，帮您看看窗外的?"）
- [ ] **2.5** 人设与场景包：`packs/elder_cn_v1` 生效，音色 = 0.3 克隆的温和女声
- [ ] **2.6** 起服务，跑通一轮：唤醒 → ASR → LLM → TTS → 动作

---

## 阶段 3 · 端侧（四本体）

- [ ] **3.1 Otto（ESP32-S3）**
  - [ ] WS 地址改为 `ws://192.168.31.10:8000/xiaozhi/v1/`（AP 配网页可改）
  - [ ] OTA 地址改为本地 8003（通常需 `idf.py menuconfig` 后重编译刷机）
  - [ ] 确认固件内"音乐拉取 / 版本检查"等联网行为已关闭
  - [ ] 重启后时间正确（验证 1.5 生效）
- [ ] **3.2 Reachy Mini（树莓派 5 · py-xiaozhi）**
  - [ ] WS 地址指向内网服务器
  - [ ] 离线唤醒可用（Sherpa-ONNX），作为 **L0 降级**的第一道防线
- [ ] **3.3 大亮底盘**
  - [ ] `chassis-gateway` 已启动，连 `ws://192.168.31.7:6060`
  - [ ] `self.daliang.*` 工具已在云端 MCP 注册
- [ ] **3.4 Pepper（NAOqi 人形）**
  - [ ] WS 音频链路指向内网服务器（xiaozhi 协议，与 Otto/Reachy 同）
  - [ ] **禁用 Pepper 内置云端 ASR/TTS/Dialogue**，主链路走云端 xiaozhi + GPT-SoVITS
  - [ ] 关闭 NAOqi 自动更新检查与遥测（机箱外连 SoftBank，断网会反复重试超时）
  - [ ] 确认本地中文语音包 / 中文字体已预装（离线兜底）
  - [ ] ALNavigation 拓扑地图已本地建好（离线不依赖云端地图）
  - [ ] 若 Pepper 开机需联网激活账号 → 先在有网时激活再断网（air-gapped 前置条件）
  - [ ] 失联看门狗：网关 ↔ 云端断连 > N 秒 → `self.pepper.stop_all`

---

## 阶段 4 · 断网验收（**决定性一步**）

- [ ] **4.1** 阻断出站（二选一）
  - [ ] 服务器默认网关指向黑洞：`ip route replace default via 192.168.31.254`（不存在的地址）
  - [ ] 或防火墙阻断该机全部出站（保留内网段）
- [ ] **4.2** 完整跑一轮：唤醒 → 说话 → 出声 → 动作
- [ ] **4.3** **抓漏网请求**（本 checklist 最有价值的一步）
  - [ ] 观察日志中所有 `timeout / ConnectionError / NameResolutionFailure` 的域名
  - [ ] Windows：`netstat -anob | findstr ESTABLISHED` 看有无非内网连接
  - [ ] Linux：`ss -tnp` 或 `tcpdump -i any not net 192.168.31.0/24`
  - [ ] **每一个超时请求都是一个未清零的联网点，回到阶段 2/3 修**
- [ ] **4.4** 断电重启测试：服务器 + 机器人全断电再上电，能自动恢复到可对话
  - [ ] 重点看 ESP32 时间、Ollama 自启、TTS 服务自启
- [ ] **4.5** 恢复网络，记录本次发现的漏网点，回填 ADR-011 §决策 4

---

## 阶段 5 · chassis-gateway 与失联急停

- [ ] **5.1** 部署位置：已外移到常开设备（推荐）**或** 4090 上独立容器 + `restart: always`
- [ ] **5.2** 心跳看门狗已接：gateway ↔ 大脑 断连 > N 秒 → 自动 `softScram`
  - [ ] N 建议 15–30s（短于巡游一个点位的行走时间）
- [ ] **5.3** 该规则已写入 `packs/elder_cn_v1/safety.yaml`，不依赖人工按急停
- [ ] **5.4** 实测：kill 掉大脑进程 → 底盘应在 N 秒内停止并保持可恢复

---

## 阶段 6 · 长期运维

- [ ] **6.1** UPS：服务器 + 路由器 + AP 接不间断电源（假期/断电场景）
- [ ] **6.2** 三级降级已就位（ADR-011 §决策 5）
  - [ ] L0 云端全挂 → 端侧离线唤醒 + 预置话术
  - [ ] L1 LLM 挂 → 关键词规则兜底
  - [ ] L2 TTS 挂 → 蜂鸣 + 动作替代
- [ ] **6.3** 教学场景：按 device_id 记录本地资源占用（沿用小歪用量看板思路）
- [ ] **6.4** 每学期初同步上游 `upstream`（ADR-003 fork 纪律），**同步后重跑阶段 4**

---

## 常见翻车点速查

| 现象 | 原因 | 修法 |
|---|---|---|
| 断网后机器人能听懂但不说话 | TTS 还是 EdgeTTS | 阶段 2.2 |
| 断网后首次连接很慢/超时 | 固件在重试官方 OTA | 阶段 3.1 |
| 闹钟/提醒全乱，记忆时间错乱 | ESP32 无 RTC 且无内网 NTP | 阶段 1.5 |
| 问天气时长时间无响应 | 天气插件在等公网超时 | 阶段 2.4 |
| 有人训练模型时机器人失控 | gateway 与大脑同机被拖垮 | 阶段 5.1 |
| Pepper 断网后动作卡死 / 反复重试 | NAOqi 遥测/更新在等外连超时 | 阶段 3.4 |
| Pepper 断网后动作卡死 / 反复重试 | NAOqi 遥测/更新在等外连超时 | 阶段 3.4 |
| 服务起不来，报显存不足 | 8B 按 FP16 加载 / 多框架抢显存 | 阶段 1.3 + ADR-011 §决策 2 |
