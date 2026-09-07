# daliang/companion-app/ — 大亮表现层 APK

**参考基线**：`xuan2261/xiaozhi-ai-android`（原生 Kotlin + Compose，协议文档齐全）
**AEC/NS 移植源**：`douo/xiaozhi-android` ｜ **许可证**：Apache-2.0 ｜ **状态**：⛔ 等尽调函回复定分支（ADR-009）

## 三条分支（由尽调函回复决定）

| 分支 | 内容 | 前提 |
|---|---|---|
| **B1** | 本模块：标准安卓 API 实现听/说/看/表情 | 可装 APK、不强制签名 |
| **B1+B3** | APK 为主，外挂硬件补缺的接口（如表情屏） | 部分 |
| **纯 B3** | 本模块降级为薄壳或废弃，外挂 SBC 交互头跑 `../../client-py` 同款栈 | 全堵 |

## 架构纪律（B1 分支下的结构）

```
companion-app/
├── app/src/main/java/suiyue/daliang/
│   ├── bridge/VendorSdkBridge.kt   # ★ 唯一允许依赖厂商 SDK 的文件
│   ├── surface/SuiyueSurface.kt    # 自有接口：AudioSink/DisplaySink/CameraSource/ExpressionSink
│   ├── audio/                      # AudioRecord PCM 上行 / AudioTrack TTS 下行 / AEC（WebRTC 移植）
│   ├── display/                    # 11.6" 主屏 kiosk + 表情屏 Presentation（或 Live2D）
│   ├── camera/                     # Camera2 按需抽帧
│   └── mcp/                        # self.suiyue.emote 等工具的端侧实现
└── README.md
```

**换厂商 SDK 版本时只改 `VendorSdkBridge.kt` 一个文件。**

## 必须做的两件事

1. **AEC 回声消除是刚需**：大亮 10W×2 喇叭 + 4–6 麦 360°，自说话自拾音会形成
   回声自激 → 免唤醒链路"自己和自己聊天"；
2. 与出厂 App 的共存/替换策略（尽调函 D1/B3 问清后再定 Launcher 方案）。
