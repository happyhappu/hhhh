# firmware-esp32/ — Otto 线端侧固件

**上游**：`78/xiaozhi-esp32`（MIT）｜ **许可证**：Apache-2.0 ｜ **状态**：待 fork

## Fork 步骤（在自己已认证的终端执行）

```bash
# 1. 在 GitHub 上 fork https://github.com/78/xiaozhi-esp32
git clone https://github.com/<你的账号>/xiaozhi-esp32.git firmware-esp32
cd firmware-esp32
git remote add upstream https://github.com/78/xiaozhi-esp32.git

# 2. 编译目标板（Otto 板级上游已内置）
#    ESP-IDF 建议 WSL2 Ubuntu；Windows 编译慢且驱动坑多
idf.py set-target esp32s3
idf.py menuconfig    # 选择 otto-robot 板型，填 WiFi 与服务器地址
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
