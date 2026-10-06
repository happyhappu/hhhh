# client-py/ — Reachy Mini 线端侧

**上游**：`huangjunsen0406/py-xiaozhi`（MIT，© 2025 Junsen）｜ **许可证**：Apache-2.0 ｜ **状态**：待 fork

## 采用两阶段：先 zip 验证，再正式 fork

> **为什么不能只下载 zip 就完事**：本目录位于 `suiyue/` 代码树内，zip 版没有版本信息，
> 提交进本仓后会与你自己的代码混进同一 git 历史。Reachy 端跑在**树莓派 5**上，
> 而协议（xiaozhi WS）与上游客户端版本相关 —— 上游一更新，zip 版就得手工比对替换，很痛。
>
> 岁悦对 Reachy 的改造同样以**新增文件/目录**为主（见下节），fork 合并上游时基本零冲突。

### 阶段一 · zip 快速验证（先确认协议链路通）

1. GitHub → `huangjunsen0406/py-xiaozhi` → Releases → `Source code (zip)`，下载
2. 解压到 `D:\WorkBuddy\桌面陪伴机器人\suiyue\client-py\`（覆盖本文件，先挪到桌面留底）
3. 在树莓派 5 上（或本机先试）**跑CLI 模式**验证语音链路能连上 xiaozhi server
4. 目标：**先确认 ASR/LLM/TTS 语音链路通**，GUI 与情感层后置

### 阶段二 · 正式 fork（长期维护姿势）

在你**已认证的终端**执行（本沙箱无 GitHub 凭据，远程操作必须你来）：

```bash
# 1. 在 GitHub 网页上 fork https://github.com/huangjunsen0406/py-xiaozhi 到你的账号

# 2. 删掉阶段一 zip 版，clone 你的 fork
cd D:\WorkBuddy\桌面陪伴机器人\suiyue
rmdir /s /q client-py
git clone https://github.com/<你的账号>/py-xiaozhi.git client-py
cd client-py

# 3. 绑定上游
git remote add upstream https://github.com/huangjunsen0406/py-xiaozhi.git
git remote -v

# 4. 建自己的开发分支
git checkout -b suiye/reachy-emote
```

> **submodule 提醒**：与 Otto 同理，`client-py/` 是**独立克隆的嵌套仓库**，
> 岁悦改造代码提交在**py-xiaozhi 自己的 fork 仓库**里，本仓只保留此`FORK.md` 作索引，
> 不要在本仓 `git add client-py/`。

## 岁悦改造点

1. **`suiyue/reachy_emote.py`**：注册 MCP 工具 `self.suiyue.emote` /
   `self.reachy.emote`，映射 6-DOF 头 + 天线 + LED 眼（映射表 =
   `../brain/capabilities/reachy_mini_v1.yaml`）；
2. **`suiyue/screen/`**：4.3–5" HDMI 内容屏，加载本地 Web 模板（适老化大字 UI，
   Chromium kiosk 全屏）——与 Otto 线、大亮 11.6" 屏共用同一套响应式 Web 模板；
3. 免唤醒链路：VAD 人声门控 + 视觉在场门控（上游已具备基础能力）。

## 硬件注意

- 屏走 **HDMI**（不要 DSI：排线短且脆弱）；树莓派 5 需 micro-HDMI 转接线；
- LED 眼管情感与注视，屏只管内容——两个"脸"分工，别混。
