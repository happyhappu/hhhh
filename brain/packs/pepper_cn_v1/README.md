# 场景包 pepper_cn_v1（骨架）

Pepper 本体的场景层。结构遵循 ADR-007（persona / agents / safety 三层 + 可选 mobility / physical_caps）。

- 域逻辑（老人陪伴）与 `elder_cn_v1` 同源，本包只做 Pepper 物理表达调校；
- 能力/动作原语以 `brain/capabilities/pepper_v1.yaml` 为准；
- 当前为 **骨架**：字段起草，待真机联调（见 `suiyue/pepper/真机联调checklist.md`）后填实。

## 文件

| 文件 | 内容 |
|---|---|
| `persona.yaml` | 人格 + emotion→motion 曲线 + 平板问候 |
| `safety.yaml` | 域安全（同 elder）+ Pepper 物理安全层 |
| `agents/companion.yaml` | 在场陪伴主 Agent（靠近/平板/健康关怀） |
| `mobility.yaml` | 巡游点位 / geofence（移动本体） |
| `physical_caps.yaml` | 物理动作能力声明 |

## 待办

- [ ] 真机验证 emotion→动作标签（Wave / Crouch / head_tilt 在 NAOqi 2.5.x 实际动画名）
- [ ] `mobility.patrol.points` 填真实 ALNavigation 拓扑节点
- [ ] geofence 禁区坐标（卧室/卫生间）
- [ ] 与云端编排器对接（`pepper_v1.yaml` → `SuiyueBrain` 路由）
