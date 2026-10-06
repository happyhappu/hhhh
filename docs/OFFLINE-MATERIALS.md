# 4090 离线物料准备清单（air-gapped 前必做）

> **为什么必须提前做**：全离线部署后**无法联网补任何物料**。ADR-011 §决策 5 明确
> "模型权重 / Docker 镜像需联网下载"是八项隐形联网点之一 —— 漏备则整机无法启动。
>
> **时机**：4090 **还能联网时**做（现在就可以，部分可在 Windows 下载后拷贝）。
>
> **依据**：`docs/adr/ADR-011-全离线部署基线.md`（选型与显存预算）+
> `xiaozhi-esp32-server-0.9.7/main/xiaozhi-server/config.yaml`（**真实配置项与行号**）+
> `requirements.txt`（真实依赖版本）。
>
> **用法**：逐条勾。下载完记录校验和，便于日后复现。

---

## 0. 先改配置：把联网模块换成本地（v0.9.7 真实行号）

> **先看这一节再下载** —— 改完配置才知道要备哪些物料。
> 下表左列是 `main/xiaozhi-server/config.yaml` 的真实行号（v0.9.7 核对过）。

| 模块 | 现状（默认） | 改为 | 行号 | 说明 |
|---|---|---|---|---|
| `selected_module.TTS` | `EdgeTTS`（**联网**） | `GPT_SOVITS_V3` | L243 | **头号必改项**，EdgeTTS 走微软服务器 |
| `selected_module.LLM` | `ChatGLMLLM`（**联网**） | `OllamaLLM` | L239 | 配置**已内置** `OllamaLLM`（L664，`type: ollama`），只改名字即可 |
| `selected_module.Memory` | `nomem` | `mem_local_short` | L245 | 隐私要求；本期可先保持 `nomem` |
| `selected_module.ASR` | `FunASR` | **不变** | L237 | 本地模型，已满足 |
| `selected_module.VAD` | `SileroVAD` | **不变** | L235 | 本地模型，已满足 |
| `selected_module.Intent` | `function_call` | **不变** | L251 | 由本地 LLM 承担 |

> ✅ **好消息（2026-10-06 核对v0.9.7 实测）**：上游**已内置本地 TTS 适配器**，
> 不需要自己写：
> - `GPT_SOVITS_V3`（L948，`type: gpt_sovits_v3`，`url: http://127.0.0.1:9880`）
> - `GPT_SOVITS_V2`（L922）
> - `FishSpeech`（L900）
> - `CosyVoiceSiliconflow`（L863）
>
> 即 ADR-011 §决策 4 第 1 项只需**改配置指向本地 GPT-SoVITS 服务**，而非写适配器。
>
> ⚠️ 但 `GPT_SOVITS_V3` 默认 `refer_wav_path: caixukun.wav`（L956）是**上游示例音频**，
> 必须换成**老人场景的温和女声克隆**（ADR-011 要求）。

---

## 1. 大模型权重（LLM）

**目标**：Qwen3-8B Q4（主力 5–6GB）+ Qwen3-14B Q4（高价值 ~9GB），见 ADR-011 §决策 2。

- [ ] **主力**：Qwen3-8B Q4_K_M（Ollama 格式）
      ```bash
      # 在有网的机器上pull 后导出
      ollama pull qwen3:8b
      # 导出 GGUF/或直接拷贝 ollama 存储目录 ~/.ollama/models
      ```
- [ ] **高价值**（可选，按需加载）：Qwen3-14B Q4
      ```bash
      ollama pull qwen3:14b
      ```
- [ ] **Embedding**（CPU 即可，ADR-011 选bge-small-zh-v1.5，约 0.2GB）
- [ ] 记录实际文件大小 → 填入下方校验表

> **显存硬纪律**（ADR-011 §决策 2）：**禁止用 transformers 默认 FP16 加载 8B**
>（16GB，单卡即满）。一律走 Ollama / vLLM / llama.cpp **量化**。
>
> ⚠️ Ollama 备料注意：Ollama 默认从 ollama.com 拉模型。air-gapped 下需
> `ollama pull` 时指向**本地文件**（`Modelfile` + `FROM ./xxx.gguf`），
> 单纯拷贝 `~/.ollama/models` 目录也可行，但要用同一版本 ollama 读取。

---

## 2. ASR 模型（FunASR SenseVoiceSmall，约 1.5GB）

配置项：`ASR.FunASR.model_dir: models/SenseVoiceSmall`（L361）

- [ ] SenseVoiceSmall 模型 → 放到**部署目录**下的 `main/xiaozhi-server/models/SenseVoiceSmall/`
      （即配置的相对路径 `models/SenseVoiceSmall`）
- [ ] 来源：ModelScope `iic/SenseVoiceSmall` 或 `FunAudioLLM/SenseVoiceSmall`
- [ ] 备选（更轻量，ADR-011 提及）：sherpa-onnx 版
      → `ASR.SherpaASR.model_dir: models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17`（L384）

> `requirements.txt` 已含 `funasr==1.2.7` / `modelscope==1.39.1` / `sherpa_onnx==1.12.29`，
> 依赖已备，无需另下。

---

## 3. VAD 模型（SileroVAD，体积小）

配置项：`VAD.SileroVAD.model_dir: models/snakers4_silero-vad`（L610）

- [ ] SileroVAD 模型 → `main/xiaozhi-server/models/snakers4_silero-vad/`
      （注意上游目录名拼写 `snakers4`，保持一致）
- 依赖 `silero_vad==6.2.1` 已在 requirements

---

## 4. TTS 模型（GPT-SoVITS V3，约 2.5GB）★ 头号必改

配置项：`TTS.GPT_SOVITS_V3`（L948-967）

- [ ] **GPT-SoVITS 权重**（V3 / v3lora-20250228，见 L949 注释）
- [ ] **老人音色参考音频**：把 `refer_wav_path`（L956，默认 `caixukun.wav`）
      换成**克隆的温和女声** wav+ 填 `prompt_text`（L958）
- [ ] GPT-SoVITS 服务端能起：`python api.py`（L951 注释），默认 `http://127.0.0.1:9880`
- [ ] 确认部署机满足 GPT-SoVITS 依赖（PyTorch 版本按 GPT-SoVITS 官方要求，
      **与 server 的 `torch==2.2.2` 可能冲突** → 建议 TTS 独立进程/容器）
- ⚠️ **推理显卡**：GPT-SoVITS 与 LLM/ASR **同卡** 时注意显存叠加（ADR-011 预算 2.5GB）

---

## 5. 声音克隆参考音频（老人音色）

- [ ] 准备 1 段**温和女声**参考音频（10–20s，干净无背景音）
- [ ] 填入`TTS.GPT_SOVITS_V3.refer_wav_path` + `prompt_text` + `prompt_language`

---

## 6. Docker 镜像（若用 docker 部署）

- [ ] `docker save` 成 tar，air-gapped 后 `docker load`
      ```bash
      docker images# 看当前用了哪些
      docker save -o xiaozhi-server-images.tar <image1> <image2> ...
      ```
- [ ] FunASRServer 路线需要（config L366-380 给的镜像）：
      `registry.cn-hangzhou.aliyuncs.com/funasr_repo/funasr:funasr-runtime-sdk-online-cpu-0.1.12`
      > 若用 `FunASR`（本地进程，非 Server），**不需要此镜像**

---

## 7. Python 依赖（离线 wheel 包）

`requirements.txt` 共 40+ 包，含 `torch==2.2.2` 等大件。**联网时预下载 wheel**：

- [ ] 在同Python 版本的干净环境执行：
      ```bash
      pip download -r requirements.txt -d wheels/    # 注意：需 Linux 平台的包
      ```
      >⚠️ 必须在 **Linux x86_64 + 对应 Python 版本**下download（Windows 下的 wheel 不可用）
- [ ] air-gapped 后：`pip install --no-index --find-links=wheels/ -r requirements.txt`
- [ ] 特别关注大件：`torch` / `torchaudio` / `funasr` / `sherpa_onnx` / `numpy`

---

## 8. 岁悦大脑侧依赖（较轻）

`suiyue/requirements-dev.txt`：`websockets>=14` / `PyYAML>=6` / `websocket-client`

- [ ] 同样 `pip download` 备 wheel（量小，很快）

---

## 9. 端侧/本体物料（各自仓，勿混）

| 物料 | 用途 | 备注 |
|---|---|---|
| `firmware-esp32` 编译产物 | Otto 烧录 | 见 `firmware-esp32/FORK.md` |
| `client-py` + 树莓派系统 | Reachy 运行 | 见 `client-py/FORK.md` |
| `pynaoqi SDK` 2.5.7.1 | Pepper 网关机 | **已在工作区**（`pynaoqi-python2.7-2.5.7.1-win32-vs2013/`） |
| 适老化 Web 模板（OTA/屏） | 四本体共用大字体 UI | 需本地托管，禁CDN |

> 屏显/前端资源**必须本地托管** —— CDN 是隐形联网点。

---

## 10. 交付前核验（air-gapped 自检）

- [ ] 断网后完整跑通一轮对话（ASR → LLM → TTS 全本地）
- [ ] 记录"所有超时请求" = 漏网的联网点（ADR-011 §决策 5 方法）：
      把默认网关指向黑洞或防火墙阻断出站 → 跑一轮 → **日志里所有超时就是漏网点**
- [ ] 把本清单勾选结果与实际文件大小记入 `brain/mcp/XIAOZHI_SERVER_PATCHES.md` §1

---

## 附：物料校验表（下载后回填）

| 物料 | 版本/来源 | 大小 | 校验和(SHA256) | 到位 |
|---|---|---|---|---|
| Qwen3-8B Q4 | ollama | | | ☐ |
| Qwen3-14B Q4（可选） | ollama | | | ☐ |
| bge-small-zh-v1.5 | HF/ModelScope | | | ☐ |
| SenseVoiceSmall | ModelScope | | | ☐ |
| SileroVAD | 上游 models/ | | | ☐ |
| GPT-SoVITS V3 权重 | 官方 | | | ☐ |
| 老人音色参考音频 | 自备/克隆 | | | ☐ |
| Docker 镜像 tar | 本地 save | | | ☐ |
| Python wheels | pip download | | | ☐ |
| pynaoqi SDK 2.5.7.1 | 工作区已有 | | | ☐ |
