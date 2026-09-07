# client-py/ — Reachy Mini 线端侧

**上游**：`huangjunsen0406/py-xiaozhi`（MIT，© 2025 Junsen）｜ **许可证**：Apache-2.0 ｜ **状态**：待 fork

## Fork 步骤

```bash
git clone https://github.com/<你的账号>/py-xiaozhi.git client-py
cd client-py
git remote add upstream https://github.com/huangjunsen0406/py-xiaozhi.git
# 树莓派 5（Reachy Mini Wireless 自带）上运行；先跑 CLI 模式验证语音链路，再上 GUI
```

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
