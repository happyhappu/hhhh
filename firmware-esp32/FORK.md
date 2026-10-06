# firmware-esp32/ — Otto 线端侧固件

**上游**：`78/xiaozhi-esp32`（MIT）｜ **许可证**：Apache-2.0 ｜ **状态**：待 fork

## 采用两阶段：先 zip 验证，再正式 fork

> **为什么不能只下载 zip 就完事**：本目录位于 `suiyue/` 代码树内。zip 解压进来的代码**没有版本信息**，
> 一旦提交进本仓，就与你自己的代码混进同一个 git 历史 —— 而上游 `78/xiaozhi-esp32`
> 27.9k star、**几乎每月一个 release**，日后"上游更新了 N 个 commit"只能手工 diff 覆盖，反复踩坑。
>
> **好消息**：岁悦对 Otto 的改造是**纯新增文件**（见下节），fork 合并上游时**零冲突**
>（上游不会碰你新加的文件）。所以走fork 的成本很低。

### 阶段一 · zip 快速验证（先确认能编译/能烧，不卡git 流程）

先花 10 分钟确认"这条路走得通"，再投入 fork 的精力。

1. GitHub → `78/xiaozhi-esp32` → Releases → `Source code (zip)`，下载
2. 解压到 `D:\WorkBuddy\桌面陪伴机器人\suiyue\firmware-esp32\`（覆盖本文件，先把它挪到桌面留底）
3. 按下方"编译目标板"用 ESP-IDF 编译，**目标：先编译通过**
4. 确认 `main/boards/otto-robot/` 存在（这是 Otto 板级支持；若上游改名/移除需重新定位）

> 阶段一目的是**验证工具链 + 板级定义**，不追求跑通全部功能。
> 验证通过后进入阶段二，把zip 版删掉重来（干净起步，避免混淆）。

### 阶段二 · 正式 fork（长期维护姿势）

在你**已认证的终端**执行（本沙箱无 GitHub 凭据，远程操作必须你来）：

```bash
# 1. 在 GitHub 网页上 fork https://github.com/78/xiaozhi-esp32 到你的账号

# 2. 删掉阶段一的 zip 版，clone 你的 fork
cd D:\WorkBuddy\桌面陪伴机器人\suiyue
rmdir /s /q firmware-esp32
git clone https://github.com/<你的账号>/xiaozhi-esp32.git firmware-esp32
cd firmware-esp32

# 3. 关键：绑定上游，之后才能 git pull 跟版本
git remote add upstream https://github.com/78/xiaozhi-esp32.git
git remote -v          # 确认 origin=你的fork / upstream=官方

# 4. 建自己的开发分支（不要直接在 main 上改）
git checkout -b suiye/otto-emote

# 5. 加岁悦改造文件（纯新增，见下节），然后
git add .
git commit -m "feat(otto): 岁悦情感映射层 + MCP emote 工具"
```

> **子模块/submodule 提醒**：`firmware-esp32/` 是**独立克隆的嵌套仓库**（自带 `.git`），
> 不属于本仓 `suiyue/` 的版本管理范围。你在本仓 `git status` 里会看到它显示为
> untracked/嵌套仓库（或 gitlink）。**不要**在本仓里 `git add firmware-esp32/` ——
> 岁悦的改造代码提交在** Otto 自己的 fork 仓库**里，本仓只保留这个 `FORK.md` 作为说明与索引。

### 编译目标板

```bash
# ESP-IDF 建议 WSL2 Ubuntu；Windows 编译慢且驱动坑多
idf.py set-target esp32s3
idf.py menuconfig    # 选择 otto-robot 板型，填WiFi 与服务器地址
idf.py build flash monitor
```

## 岁悦改造点（目标 < 200 行 C++）

上游 `main/boards/otto-robot/` 已有：4–6 舵机、28 种 ActionType、Oscillator 正弦插值、
动作队列、摄像头变体自动检测、MCP 工具（`self.otto.action/stop/get_status/...`）、
`:8080` WebSocket 控制服务器。**动作能力是白送的，我们只写情感映射层：**

```
suiyue/
├── emotion_map.cpp/.h     # {emotion,intensity} → 保守动作子集（查 brain/capabilities/otto_v1.yaml 的映射表）
├── mcp_suiyue.cpp         # 注册 self.suiyue.emote 工具（契约见 docs/MCP-CONTRACT.md）
└── README.md
```

## 烧录注意（踩过的坑）

- bootloader 顺序：**先接电池 → 电源 OFF → 按住 boot → 开电源 → 松开**，顺序反了烧不进去；
- 烧录后看 monitor 走哪个硬件分支（官方 PCB 走"不带摄像头"分支：LL=17/RL=39/LF=18/RF=38）；
- BOM / 避坑（3D 件必须 v1.3、麦克风 ZTS6672、功放非 BGA）见 `../../hardware/README.md`。

## 上游安全约束（沿用）

双腿摆幅 ≥ 40° 强制归零；跳跃/太空步/大风车只进 showcase、不进老人场景动作子集。
