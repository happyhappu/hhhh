# ADR-009 大亮：双网关拆分 + 三级自主兜底

日期：2026-09-07 ｜ 状态：已接受（依赖尽调函结果收敛分支）

## 事实
大亮 = 深圳易行(EGO) AGV 底盘（L4 满级开放：导航/地图/充电/巡游/事件导航/软急停/geofence，明文 JSON over WS:6060/MQTT:1883）+ 整机厂 Android 上位机（听/说/看/表情接口**未知**）。

## 决策 1：拆成两个独立件
- `daliang-chassis-gateway`：纯网络协议，跑在任何同局域网设备上，**不必在大亮上**。接口已齐，基于 Mock Server 可立即开发；
- `daliang-companion-app`：跑在大亮 Android 上，是唯一依赖厂商 SDK 的地方（`bridge/VendorSdkBridge.kt` 单点隔离）。

## 决策 2：上位机三级兜底（Plan B）
| 分支 | 做法 | 前提 | 成本 |
|---|---|---|---|
| B1 | 标准 Android API（AudioRecord/Camera2/Presentation）自研 APK | 可装 APK、不强制签名 | ¥0 |
| B2 | adb 探测 + disable-user 释放资源 | 开放 ADB | ¥0（注意质保） |
| B3 | 外挂 SBC 交互头（麦阵列+扬声器+屏），大亮退化为移动底盘 | 无 | ¥600–1500 |

B3 的意外收益：外挂 SBC 跑 Reachy 同款 Python 栈，**四条本体线软件栈彻底统一**。

## 决策规则修正
底盘 L4 + B3 成立 ⇒ **采购不再被上位机接口一票否决**；尽调函回复只决定走哪条分支与议价筹码。
不变量：Mock Server、chassis-gateway、云端能力注册、场景包骨架，任何分支下都要做。
