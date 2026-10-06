# xiaozhi-esp32-server · 岁悦 overlay 补丁台账（PATCHES）

> **用途**：`xiaozhi-esp32-server` 是**外部项目**（`xinnan-tech/xiaozhi-esp32-server`，MIT），
> 不 fork、不纳入 `suiyue/` 仓库，而是**整体部署在 4090 上**。
> 我们只按"薄改动"纪律改 3 处，其余保持上游原样。
>
> **本文件是这3 处改动的唯一台账**：记录基于哪个上游版本、改了什么、怎么回滚。
> 上游发新版本时，照本文件逐条重做即可（薄改动，代价可控）。
>
> **改动详细设计**见同级`GET_SCENE_OVERLAY_GUIDE.md`（X1/X2/X3 示意代码、时序、字段映射、降级策略）。
> 本文件只做"记账"，不重复设计。

---

## ⚠️ 为什么用 zip 而不 fork

| 维度 | 说明 |
|---|---|
| 部署形态 | 整体替换的**外部服务进程**，不嵌进 `suiyue/` 代码树，没有"合并上游"的需求 |
| 改动性质 | 3 处薄改动（overlay 纪律：只加自己的逻辑，不跟踪上游内部） |
| 上游节奏 | 0.x 阶段，三个月三个版本（v0.9.5→ v0.9.7），且有**破坏性配置变更** |
| 同步成本 | 每次升级只需重做 3 处 + 核对本台账，不必解冲突 |

> 若将来需要**回传上游**（给xinnan 提 PR），那时再改为 fork；本项目定位是"自用改造"，不回传。

---

## 1. 版本台账

**每次下载/升级都先在此记录版本号**，否则日后无法复现"当时跑的是哪版"。

| 日期 | 上游版本(tag) | 部署机 | 部署路径 | 备注 |
|---|---|---|---|---|
| 2026-10-06 | ✅ **v0.9.7** | 本机（阅读/分析） | `D:\WorkBuddy\桌面陪伴机器人\xiaozhi-esp32-server-0.9.7\` | 从 Releases `v0.9.7` 的 `Source code (zip)` 解压，**目录名即版本**。结构 7/7 完整，server 目录 229 文件。⚠️ zip 无 `.git`；若需 `git diff` 看自己改动，改用 `git clone --branch v0.9.7` |
| ~~2026-10-06~~ | ~~main 分支（非 tag）~~ | — | ~~`xiaozhi-esp32-server\`~~ | **已废弃**（无版本信息、无法复现）；下载 tag 版后该目录已移除 |

> **核对结论（2026-10-06）**：`v0.9.7` 与此前 main 版的 overlay 三个落点**行号完全一致**
> （`config.yaml` L119-121 / `mcp_manager.py` L34,49,78 / `prompt_manager.py` L76,249），
> 说明这几个文件在 0.9.7 → main 之间未变，§2 台账里的行号**对 v0.9.7 有效**。
>
> **换版本后复核方法**（一次输出结构/版本/X1-X3 落点/MCP 注册位）：
> ```bash
> python suiyue/tools/inspect_xiaozhi_server.py "D:\WorkBuddy\桌面陪伴机器人\xiaozhi-esp32-server-0.9.7"
> ```

### 部署路径说明（别和项目目录混淆）

> **`/opt/xiaozhi-esp32-server` 在「4090 服务器」上，不在项目根目录里。**

本项目（`suiyue/`）的三者位置必须分清：

| 位置 | 跑什么 | 说明 |
|---|---|---|
| **4090 服务器**（Linux，与机器人同局域网） | `xiaozhi-esp32-server` + 大模型 + 大脑 MCP server | **本文档讨论的 overlay 就在这里**。这是「仓库外的部署物」，不纳入 `suiyue/` 版本管理 |
| **`D:\...\suiyue\`**（你的 Windows 开发机） | 大脑侧代码（`brain/`）、各本体适配层、单测/e2e | 项目源码仓|
| **本体设备**（Otto / Reachy / 大亮网关 / Pepper 网关机） | 端侧固件/客户端 | 由本体仓各自维护（见 `firmware-esp32/FORK.md`、`client-py/FORK.md`） |

- 建议部署路径用绝对路径 `/opt/xiaozhi-esp32-server`（root 拥有、与项目解耦，
  便于整机备份/迁移；**不放在项目目录下**，避免与源码仓混淆、被`git add` 误收编）。
- 若你习惯把源码也留在 4090 上便于查看，**放 `/opt/` 或 `/srv/` 下另起目录**，
  但**不要**放在 `suiyue/` 仓库路径里（源码仓应保持干净、只放你自己写的代码）。
- 部署形态按 ADR-011 为 **server-only**（文件配置、无数据库、2–4GB RAM）。
- **本地开发参照**：你也可以先在 Windows 上用 `xiaozhi-mcp-settings.example.json` 把大脑
  MCP server 拉起来单独调 `get_scene`（不启整个 xiaozhi server），
  验证"大脑侧能被拉到场景包"这一步；overlay 本身等上4090 再做。

> **下载方式**：GitHub → Releases → `Source code (zip)`，
> 或 `git clone https://github.com/xinnan-tech/xiaozhi-esp32-server.git && git checkout v0.9.x`
> （`git clone` 但**不 fork**，只在部署机上留一份便于 `git diff` 看自己的改动）。

---

## 2. 三处改动台账（✅ 已于 2026-10-06 落地并本机验证）

> ✅ **落地状态**：X1 / X2 / X3 **全部已写入源码**（Windows 侧 `xiaozhi-esp32-server-0.9.7`），
> 改动前自动备份为 `*.suiyue.bak`，可一键回滚。
> 应用脚本：`suiyue/tools/apply_overlay_x1x2.py`、`suiyue/tools/apply_overlay_x3.py`（均幂等）。
> 行号对应本机下载版；升级上游后行号会漂，但**函数名/类名稳定**，按名字找更可靠。
>
> **本机已验证**（`suiyue/overlay/test_suiyue_scene.py`，11 用例全绿）：
> stdio 链路通、`get_scene` 拿到 `pepper_cn_v1`、渲染 485 字符、缓存生效、降级正确。
> **未验证**（需 4090）：真实 xiaozhi server 进程内集成（起服务→连设备→看 LLM 实际收到 prompt）。
>
> 真实源码根（Windows 侧阅读用）：
> `xiaozhi-esp32-server/main/xiaozhi-server/`
> 部署到 4090 后对应 `/opt/xiaozhi-esp32-server/main/xiaozhi-server/`。

### X1 · 声明 device_id

- **文件**：`main/xiaozhi-server/config.yaml`（共 1175 行；**注意：不是 `suiyue/brain/mcp/config.yaml`**）
- **落点参考**：该文件第 119–121 行已有 `mcp_endpoint` 段（云端 MCP 接入点），
  可作为放置自定义 `suiyue:` 段的相邻位置
- **改动**：新增 `suiyue.device_id: pepper-01`（+约 2 行）
- **意图**：告诉 server"我是哪个本体"，会话开始调大脑 `get_scene(device_id)` 时使用
- **一致性锚点**：必须与 `suiyue/brain/mcp/config.yaml` 里已注册的 `pepper-01` 字面一致
- **回滚**：删掉这两行即可，无副作用

### X2 · 拿到大脑 MCP client 句柄 ✅ 上游已有现成机制

- **落点**：`main/xiaozhi-server/core/providers/tools/server_mcp/mcp_manager.py`
  - `ServerMCPManager.load_config()`（L34）—— 从 `mcp_server_settings.json` 读 `mcpServers`
  - `ServerMCPManager.initialize_servers()`（L78）—— **并发初始化所有 MCP server**
  - `ServerMCPManager._init_server()`（L49）—— 单个 client 建立，**10s 超时**（L57）
  - 句柄存在 `self.clients[name]`（L61），工具清单在 `self.tools`（L63）
- **改动**：**零代码改动**，已在 `mcp_server_settings.json` 的 `mcpServers` 注册
  `suiyue-brain`（stdio，`command: python3` + `args: [-m, brain.mcp, --config, ...]`）。
  上游原生支持 stdio / sse / streamable-http 三种传输。
- **实际改动文件**：`mcp_server_settings.json`（备份 `mcp_server_settings.json.suiyue.bak`）
- **部署注意**：`args` 里的 `brain_repo` 路径需按部署机改（4090 上为 `/opt/suiyue`）
- **回滚**：删除 `mcpServers["suiyue-brain"]` 条目，或用 `.bak` 覆盖

### X3 · 会话开始调 get_scene 注入 prompt ✅ 已落地

- **注入器（本仓维护）**：`suiyue/overlay/suiyue_scene.py`
  （已复制到 server 的 `main/xiaozhi-server/core/suiyue_scene.py`）
  - `render_scene_prompt(scene)` — 场景包 → prompt 文本
  - `inject_scene_into_prompt(config, device_id)` — 同步入口，**永不抛异常**
  - `warmup(config)` — **后台预热**（见下方性能说明）
- **上游改动仅 2 处**（`core/connection.py`，备份 `connection.py.suiyue.bak`）：
  1. L42-48 顶部 import（try/except 兜底，overlay 缺失时上游行为不变）
  2. L670-683 `_init_prompt_enhancement()` 内改用注入后的 `base_prompt`
- **落点依据**：`build_enhanced_prompt()`（`prompt_manager.py:249`）把入参直接喂给
  模板的 `{{base_prompt}}` 占位符（`agent-base-prompt.txt:4` 的 `<identity>` 段），
  所以**只需在调用前拼好 base_prompt，不必改prompt_manager**。
- **字段路径**：返回体 `persona` 是**双层嵌套** —— `scene["persona"]["persona"]["name"]`。
  `emotion_calibration` **不进 prompt**（端侧 emotion→motion 曲线，与 LLM 文本无关）。

> ⚠️ **实测性能（重要）**：首次 stdio 调大脑 MCP 需**约 13 秒**
> （拉起子进程 + 加载场景包 + 大亮底盘连接超时重试）。
> → 已在注入器提供 `warmup()`，应在 server 启动时后台线程预热，
> 让首个真实会话走缓存（约 0.000s）而不是等13 秒。
> `MCP_TIMEOUT_S=30.0`（给足余量）；任何失败都**回退原始 prompt**，不影响会话。
>
> 接入方式（上游 `app.py` 启动处，可选但强烈建议）：
> ```python
> import threading
> from core.suiyue_scene import warmup
> threading.Thread(target=warmup, args=(config,), daemon=True).start()
> ```

> ⚠️ **暴露工具边界（2026-10-06 实测确认，必须遵守）**：
> 只暴露大脑**已注册**的工具（`self.suiyue.*` / `self.daliang.*`），**不要把场景包 agent
> 声明的 `tools` 整份塞给 LLM**。
>
> 实测（`tools/precheck_brain_mcp.py`）发现 `pepper_cn_v1` 的 agent 声明了 **8 个未注册工具**：
> - `companion`：`self.pepper.approach` / `self.pepper.tablet_render` / `self.pepper.stop_all`
>   （G6 未建，**且会与端侧 `EMOTION_TO_ACTION` 双驱动冲突**）
> - 两者共有：`profile.get` / `profile.confirm` / `knowledge.rag_search`（记忆与知识库工具，尚未建）
>
> 若整份暴露，LLM 会尝试调用不存在的工具 → 工具调用失败 → 对话中断。
> **正确做法**：X3 只把 `persona` 语气 + agent 的 `system_prompt` 文本注入 prompt，
> **工具清单由 server 侧按"已注册 ∩ 允许前缀"过滤后注入**，或干脆不注入
> （让 server 原有的 MCP 工具机制自动暴露，它已自动并入 `tool_manager`）。
>
> 复核命令：`python suiyue/tools/precheck_brain_mcp.py`（退出码 1 = 有未注册工具）

---

## 3. 升级上游时的操作顺序

1. 读上游 Release Notes，记录破坏性变更（配置字段重命名、依赖变动等）
2. 备份当前跑通的部署目录（`cp -a`，别覆盖）
3. 下载新版本 → 按 §2 逐条重做 X1/X2/X3 → 更新 §1 版本台账
4. 起 server，按 §4 验收；任一项不过则`cp -a` 回滚到备份

---

## 4. 验收（不依赖真机）

- [ ] server 能正常起来，`config.yaml` 无解析错误（X1 生效）
- [ ] server 启动日志能看到 MCP client 连上大脑（X2 生效）
- [ ] 会话开始日志能看到 `get_scene` 被调、且 `scene_pack` 解析成功（如 `pepper_cn_v1`）（X3 生效）
- [ ] 断开大脑 MCP → 会话仍能开（回退写死 prompt，不崩）
- [ ] LLM 实际收到的 system prompt 里含persona 语气与 safety 硬规则（看 server 侧 prompt 日志）

> 与 Pepper 端的联动项（G3/G4）要等真机联调才能最终确认，见 `pepper/真机联调checklist.md` §8。

---

## 5. 相关文件

| 文件 | 作用 |
|---|---|
| `GET_SCENE_OVERLAY_GUIDE.md` | 3 处薄改动的**详细设计**（示意代码、时序、字段映射、降级） |
| `../mcp/xiaozhi-mcp-settings.example.json` | 大脑 MCP server 在 xiaozhi 侧的注册样例（stdio 拉起） |
| `../mcp/config.yaml` | 大脑侧已注册本体（`pepper-01` 等），X1 的 `device_id` 须与之字面一致 |
| `../../../docs/MCP-CONTRACT.md` §8 | `get_scene` 契约定义 |
| `../../../pepper/真机联调checklist.md` §8 | G3/G4（emotion 契约 / 设备绑定）联调验收 |
