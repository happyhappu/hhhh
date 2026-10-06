# 4090 服务器部署执行清单（xiaozhi-esp32-server + 岁悦大脑）

> **适用**：单台 4090（24GB）作实验室边缘服务器，与四台机器人同一局域网，**全离线 air-gapped**。
> 依据：`docs/adr/ADR-011-全离线部署基线.md`（server-only / 2–4GB RAM）、
> `docs/adr/ADR-002-四本体一脑.md`。
>
> **当前状态（2026-10-06）**：4090 **尚不可访问**。本清单分两段——
> **A 段现在就能做**（Windows 本机，无需 4090）；**B 段上机后按序执行**。
>
> **overlay 台账**：3 处薄改动的记账在 `brain/mcp/XIAOZHI_SERVER_PATCHES.md`，
> 详细设计在 `brain/mcp/GET_SCENE_OVERLAY_GUIDE.md`。本清单只讲**部署动作**。

---

## 目录约定（先分清三处，勿混淆）

| 位置 | 放什么 | 是否 git 管|
|---|---|---|
| **4090 · `/opt/xiaozhi-esp32-server`** | xiaozhi server 本体+ overlay 改动 | ❌ 否（仓库外部署物） |
| **4090 · `/opt/suiyue`** | 大脑侧代码（brain MCP server） | ✅ 是（你的源码仓） |
| **Windows · `D:\WorkBuddy\桌面陪伴机器人\`** | 开发/联调机；`suiyue/` 源码 + 外部资料 | ✅ 源码仓 |
| **4090 · `/opt/models` + `/opt/images`** | 大模型权重 / Docker 镜像 tar | ❌ 否 |

> 原则：**源码与部署物分离**。`xiaozhi-esp32-server` 源码**不放进 `suiyue/` 仓库**。

---

## A 段 · 现在就能做（Windows，无需 4090）

### A1. 下载并解压 zip（先在Windows 看代码/做overlay）
- 下载：GitHub → `xinnan-tech/xiaozhi-esp32-server` → Releases → `Source code (zip)`
  （**务必选 tag**，如 `v0.9.7`，不要选 `main`——main 分支 zip 无版本信息、无法复现）
- 解压后文件夹名即版本号（`xiaozhi-esp32-server-0.9.7`），**保留这个版本号**，
  本机路径：`D:\WorkBuddy\桌面陪伴机器人\xiaozhi-esp32-server-0.9.7\`
  （**与 `suiyue/` 平级**，与 pynaoqi SDK、各 PDF 资料并列）
- ⚠️ **不要**放进 `suiyue/` 里面（会被 git 收编）。原因见 `CONTEXT.md`「外部本体项目」词条。
- ✅ 已完成（2026-10-06）：`v0.9.7` 已下载并核查，结构 7/7 完整，
  overlay 落点行号见 `brain/mcp/XIAOZHI_SERVER_PATCHES.md` §2
- 核查命令（换版本后重跑）：
  ```bat
  python suiyue\tools\inspect_xiaozhi_server.py "D:\WorkBuddy\桌面陪伴机器人\xiaozhi-esp32-server-0.9.7"
  ```

### A2. 记版本号（写进 PATCHES台账）
- 打开 `suiyue/brain/mcp/XIAOZHI_SERVER_PATCHES.md` §1，把下载的 tag 填进版本台账表。

### A3. 先验证大脑侧能拉到场景包（不必等 4090）
用现成的 stdio 配置把大脑 MCP server 拉起来，单独调 `get_scene`：

```bat
:: 在 suiyue\ 目录下（大脑 MCP server 以 stdio 起，配置见 brain\mcp\config.yaml）
python -m brain.mcp --config brain/mcp/config.yaml
:: 另开一个终端，用 MCP inspector 之类连 stdio，调 self.suiyue.get_scene(device_id="pepper-01")
:: 期望返回：scene_pack = pepper_cn_v1，agents = [health, companion]
```

- 这一步验证"**大脑侧 get_scene 可用**"（G5 已实装），overlay 的 X1/X2/X3 留到 B 段。
- 全部大脑侧测试也可本地跑：`cd suiyue && python -m unittest discover -s . -p "test_*.py" -t .`（应为 55 tests OK）。

### A4. 准备离线物料（ADR-011 隐形联网点#5）⚠️ air-gapped 后补不回来
**完整清单见 `docs/OFFLINE-MATERIALS.md`**（含 v0.9.7 真实配置行号与下载命令）。
最小集：
- [ ] Qwen3-8B Q4（Ollama）+ 可选 14B
- [ ] SenseVoiceSmall（ASR）、SileroVAD
- [ ] **GPT-SoVITS V3 权重 + 老人音色参考音频**（TTS，头号必改项）
- [ ] Docker 镜像 tar（若用 docker）
- [ ] Python wheels（**必须在 Linux + 对应 Python 版本下** `pip download`）
- [ ] 适老化 Web 模板本地托管（禁 CDN）

> ✅ 已核对 v0.9.7：`OllamaLLM` 与 `GPT_SOVITS_V3` **上游均已内置**，
> 只需改 `config.yaml` 指向本地服务，不必自己写适配器。

---

## B 段 · 4090 就位后按序执行

> 全程`ssh` 上 4090 操作。**B 段命令需root 权限的加 `sudo`**。

### B1. 基础环境确认
```bash
uname -a# 确认 Linux
nvidia-smi                # 确认 4090 在位、驱动正常
python3 --version         # 建议 3.10+
docker --version && docker compose version
# 内存：server-only 需 2–4GB（ADR-011）
free -h
```
- [ ] 记录 `nvidia-smi` 与 `python3 --version` 输出到 PATCHES 台账备注

### B2. 放置 xiaozhi-esp32-server（zip 或 clone）
```bash
sudo mkdir -p /opt/xiaozhi-esp32-server
cd /opt
# 方式一：直接下载 tag 版 zip（推荐，目录名带版本即锚点）
sudo wget https://github.com/xinnan-tech/xiaozhi-esp32-server/archive/refs/tags/v0.9.7.zip
sudo unzip -q v0.9.7.zip
sudo cp -r xiaozhi-esp32-server-0.9.7/* /opt/xiaozhi-esp32-server/
sudo rm -r xiaozhi-esp32-server-0.9.7 v0.9.7.zip

# 方式二：git clone 指定 tag（想用 git diff 看自己改动时更方便）
sudo git clone -b v0.9.7 --depth 1 https://github.com/xinnan-tech/xiaozhi-esp32-server.git /opt/xiaozhi-esp32-server
```
- 部署后**立即把版本号记进** `brain/mcp/XIAOZHI_SERVER_PATCHES.md` §1 台账
- 若想在4090 上核对结构/落点（需先把 tools/inspect_xiaozhi_server.py 传过去）：
  ```bash
  python3 inspect_xiaozhi_server.py /opt/xiaozhi-esp32-server
  ```

### B3. 放岁悦大脑源码
```bash
# 把 Windows 上的 suiyue/ 同步到 4090（scp / rsync / git push 后 clone，按你习惯）
sudo mkdir -p /opt/suiyue
# 例：scp -r 本地路径 suiyue user@4090:/opt/
```

### B4. 起 xiaozhi server（**先不改overlay，先跑通原版**）
- 按其README 起（通常 `docker compose up -d` 或 `python main.py`）
- 确认 server 起来、能被Otto/Reachy 端连上（如果那两台还没就位，可先只验证 server 启动）
- [ ] 记录启动方式到 PATCHES 台账备注

### B5. 做overlay 3 处（此时才改，对齐台账）
按 `GET_SCENE_OVERLAY_GUIDE.md` + `XIAOZHI_SERVER_PATCHES.md`：
- [ ] **X1** server 侧 `config.yaml` 加 `suiyue.device_id: <如pepper-01>`（与大脑 `config.yaml` 字面一致）
- [ ] **X2** MCP 初始化处留 client session 句柄
- [ ] **X3** system prompt 构造处主动调 `get_scene` 注入（失败回退写死 prompt）
- ⚠️ X3 字段路径：`scene["persona"]["persona"]["name"]`（**双层嵌套**）；`emotion_calibration` 不进 prompt
- ⚠️ 只暴露大脑已注册工具，**不暴露 `self.pepper.*`**

### B6. 接大脑 MCP server
- 用 `brain/mcp/xiaozhi-mcp-settings.example.json` 注册大脑 MCP server（stdio拉起）
- [ ] `self.suiyue.get_scene(device_id=...)` 在 server 会话开始时被调用且成功

### B7. 验收（对齐 PATCHES §4 + 离线 checklist）
- [ ] server 起得来、config无解析错（X1）
- [ ] 日志见 MCP client 连上大脑（X2）
- [ ] 会话日志见 `get_scene` 被调、`scene_pack=pepper_cn_v1`（X3）
- [ ] 断开大脑 MCP → 会话仍能开（回退写死 prompt）
- [ ] LLM 收到的 system prompt 含 persona 语气 + safety 硬规则
- [ ] 走一遍 `docs/OFFLINE-CHECKLIST.md`（内网 WS 不走代理、离线唤醒、ASR/TTS 本地等）

### B8. 接四本体
- [ ] 大亮底盘：chassis-gateway 按 ADR-011 决策3 **不部署 4090**，放同网段其它设备
- [ ] Otto / Reachy：按各自 `FORK.md` 两阶段（zip 验证 → 正式 fork）
- [ ] Pepper：按 `pepper/真机联调checklist.md` 走 §1–§7

---

## 风险与回滚

| 风险 | 应对 |
|---|---|
| xiaozhi server 升级后 overlay 被覆盖 | 每步前 `cp -a` 备份部署目录；PATCHES §4 验收不过即回滚 |
| 忘配`no_proxy` 导致内网 WS 被代理接管 | 见 `OFFLINE-CHECKLIST.md` §3.3；代码侧已 `proxy=None` 兜底 |
| 权重/镜像忘备，air-gapped 后无法补| A4 阶段务必备齐 |
| 4090 是单点故障 | ADR-011 决策5 三级降级；大模型可迁 DGX Spark（但仅作推理/微调，不做并发） |

---

## 关联文件

| 文件 | 作用 |
|---|---|
| `brain/mcp/XIAOZHI_SERVER_PATCHES.md` | overlay 台账（版本 + 3 处改动 + 升级流程 + 验收） |
| `brain/mcp/GET_SCENE_OVERLAY_GUIDE.md` | overlay 详细设计（示意代码/时序/字段映射/降级） |
| `docs/adr/ADR-011-全离线部署基线.md` | server-only 基线、显存预算、隐形联网点、三级降级 |
| `docs/OFFLINE-CHECKLIST.md` | 逐项部署验收（含内网代理项） |
| `brain/mcp/xiaozhi-mcp-settings.example.json` | 大脑 MCP server 在 xiaozhi 侧的 stdio 注册样例 |
| `brain/mcp/config.yaml` | 大脑侧已注册本体（`pepper-01` 等），X1 的 `device_id` 须与之字面一致 |
