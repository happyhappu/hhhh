# 跨本体 MCP 工具契约（v1）

> 这是"一个大脑三个身体"的宪法。云端与端侧都只认这份契约；改契约必须走 ADR。

## 1. 情感意图（所有本体必须实现）

### `self.suiyue.emote`

```json
// 云端 → 端侧（LLM 输出，经编排器下发）
{
  "tool": "self.suiyue.emote",
  "parameters": {
    "emotion": "happy",          // happy/sad/curious/concerned/neutral/excited/soothing ...
    "intensity": 0.7,            // 0.0–1.0
    "action_primitive": null,    // 可选：显式动作提示，端侧有权忽略（安全优先）
    "params": {}                 // 可选：原语参数（如目标点）
  }
}
```

端侧收到后：查自身能力注册表（`brain/capabilities/<model>.yaml`）→ 本地编排器选动作 → 执行。
**同一意图在不同本体上的表现由端侧决定，云端无权指定具体动作名。**

## 2. 大亮底盘工具（chassis-gateway 提供）

| 工具 | 参数 | 底盘命令 | 说明 |
|---|---|---|---|
| `self.daliang.navigate` | `{x, y, theta, speed?}` 或 `{marker_id}` | `navigation` / `navigationById` | 自由导航到坐标或命名点位 |
| `self.daliang.patrol` | `{points: [{marker_id, dwell_s}], loops?}` | `multiPointCruise` | 定时巡游看护，到达回调上报 |
| `self.daliang.approach` | `{marker_id}` | `eventNavigation` + `incidentRelease` | 走到点位并暂停，等云端释放（"走到老人身边说话"） |
| `self.daliang.follow` | `{mode: start/stop, gain?}` | `remoteControl` | 速度环遥控（跟随实验用） |
| `self.daliang.get_status` | `{}` | `getAgvStatus` | 位姿/电量/急停/置信度，建议 1Hz 轮询 |
| `self.daliang.stop_all` | `{}` | `softScram` | **软急停，任何 Agent 可无条件调用** |
| `self.daliang.dock` | `{}` | `charge` | 自动回桩充电 |
| `self.daliang.region` | `{op: get/set, type: wall/slowdown, points}` | `region` | 虚拟墙/减速区（geofence） |

阶段 B 追加：`vision_observe`（按需抽帧）、`screen_render`（屏内容下发）、`posture_event`（异常静止/跌倒事件上报）。

## 3. 事件上行（端侧 → 云端）

```json
{"type": "device_event", "event": "patrol_arrive", "marker_id": "sofa", "code": 1000}
{"type": "device_event", "event": "emergency_stop", "reason": "bumper"}
{"type": "device_event", "event": "battery_low", "level": 15}
```

## 4. Otto 端侧（firmware overlay 注册）

- `self.otto.emote`：同 §1 契约，映射到保守动作子集（点头/摇头/摇摆/挥手/鞠躬/害羞）；
- `self.otto.get_status` / `self.battery.get_level`：上游已有，直接复用。

**安全约束**：双腿摆幅 ≥ 40° 的动作一律强制归零；跳跃/太空步/大风车不在老人场景动作子集内（仅展示模式）。

## 5. Reachy 端侧（client-py 注册）

- `self.reachy.emote`：映射到 6-DOF 头 + 天线 + LED 眼（如 happy → 头上扬+天线摆+眯眼）；
- `self.reachy.set_screen`：5" 内容屏渲染（适老化 Web UI）。

## 6. 版本与兼容

- 契约版本随 `docs/adr/` 演进，工具新增不破坏旧端；参数变更必须升 major；
- 端侧收到不认识的原语：静默降级为 `neutral`，不报错打断对话。
