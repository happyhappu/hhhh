# 岁悦 SuiYue

一个软件大脑 + 四个机器人身体的陪伴机器人开源项目。教学载体优先，产品化为远期愿景。
本文件是项目的**统一语言（ubiquitous language）**：只定义"词是什么"，不记录"怎么实现"。

## Language

### 顶层概念

**大脑（Brain）**:
云端唯一的会话与决策中枢。它只表达"我想要什么"，从不知道某台机器人长什么样。
_Avoid_: 云端大脑（冗余"云"）、brain 服务、后台

**本体（Body）**:
一台具体的机器人。Otto / Reachy Mini / 大亮 / Pepper 共四台，各自绑定一个 `device_model`。
_Avoid_: 机器人、设备、终端、body（未加中文时用 Body）

**端侧（Edge）**:
本体上不属于大脑的那一半（固件 / 网关 / 桥 / App）。端侧 OS 透明——大脑只认小智协议 + MCP。
_Avoid_: 客户端、端上（口语可，但文档一律用"端侧"）

**云零改（Cloud-Unaware）**:
接入新本体时大脑代码不改动，只新增一份能力注册表条目。端侧 OS 透明原则的工程表述。
_Avoid_: 解耦、低耦合（太泛，指不出具体不变量）

### 意图与动作

**情感意图（Emotion Intent）**:
大脑下发给端侧的表达请求，形如 `{emotion, intensity, action_primitive?, params?}`。
云端**无权指定具体动作名**——同一意图在不同本体上表现由端侧决定。
_Avoid_: 指令、命令、emotion（单独使用时指 emotion 字段本身）

**emotion**:
情感意图的语义维度，取值 `happy / sad / curious / concerned / neutral / excited / soothing` 等。
_Avoid_: 情绪（近义，混用会破坏契约）、label、mood

**intensity**:
情感强度，0.0–1.0 连续量。同一 emotion 在不同 intensity 下动作幅度/频率不同。
_Avoid_: 音量、力度（会被误当成音频或物理量）

**动作原语（Action Primitive）**:
端侧**已命名、可被直接调用**的动作单元（如 `approach` / `navigate` / `wave`）。
区别于情感意图：原语是"做什么动作"，意图是"什么情感"。原语名不得由云端自由发明。
_Avoid_: 动作、action（未限定时）、技能

**emotion_mapping**:
能力注册表内把 emotion 映射到该本体**实际动作名**的表。它是"翻译层"，不是动作清单本身。
_Avoid_: 动作表、情绪映射表（未限定时）

**action_space**:
该本体**允许执行的动作名全集**，分 `conservative_subset`（老人场景可用）与
`showcase_only`（仅展示）。`emotion_mapping` 的取值必须是 `action_space` 的子集。
_Avoid_: 动作空间、可用动作（未限定时）

**静默降级（Silent Degradation）**:
端侧遇到不认识的原语或缺失能力时，**不报错、不打断对话**，退化为 neutral。
_Avoid_: 忽略、跳过、fallback（未限定时）

### 云端编排层

**能力注册表（Capability Registry）**:
`brain/capabilities/<device_model>.yaml`。device_model → 硬件能力 / 动作空间 / 情感映射的
机器可读映射，是 MCP-CONTRACT 的机器可读版。**云端靠它判断"这台能不能做"**。
_Avoid_: 配置文件、设备表、model 文件

**device_model**:
本体的型号标识（`otto_v1` / `reachy_mini_v1` / `daliang_v1` / `pepper_v1`）。
一个 device_model 可对应多台 device_id（一台大亮与另一台大亮型号相同）。
_Avoid_: device_id、设备类型、型号字符串

**device_id**:
单台具体本体的实例标识（如 `daliang-01`）。注册进大脑时与 device_model 一对一绑定。
_Avoid_: device、sn、序列号（sn 是硬件序列号，语义不同）

**编排器（Orchestrator）**:
云端把情感意图翻译成具体 `self.<body>.*` 工具调用的组件（如 `DaliangOrchestrator`）。
_Avoid_: Provider、适配器（Provider 是更上层的抽象，见下）

**BodyProvider**:
大脑侧"这台本体怎么执行意图"的抽象。`StaticProvider` 按注册表解析但不真执行（演示/测试）；
`DaliangProvider` 实时驱动底盘。**换本体只需换 Provider，不改大脑。**
_Avoid_: Driver、适配器、后端

**locomotion**:
本体的移动方式。`chassis`（大亮 AGV 底盘）/ `naoqi_wheel`（Pepper 三轮）/ 无此字段（Otto、Reachy 不可移动）。
**它是"本体能否响应移动类原语"的唯一判据**——不是 action_space 里有没有动作。
_Avoid_: 移动能力（含义模糊，能力由 action_space 决定）

### 场景包

**场景包（Scene Pack）**:
`brain/packs/<pack_id>/`。把 persona / safety / agents / mobility / physical_caps 五段
内容打包成一个可热切换的整体。内容**只存在大脑侧**，server 不内联任何文案。
_Avoid_: 场景、场景配置、prompt 模板

**scene_pack**:
场景包 id（如 `elder_cn_v1` / `pepper_cn_v1` / `kids_v1`）。
_Avoid_: scene_id、场景名

**persona**:
场景包的人格与表达风格部分。回答"它是谁"。
_Avoid_: 角色、人设（口语可用，文档一律 persona）

**hard_rules**:
安全硬规则，直接进 LLM system prompt 作护栏，不可被对话覆盖。
_Avoid_: 安全规则、safety（safety 是整个文件，hard_rules 是其中一个 list）

**agents**:
场景包内 Agent 集合，每个 Agent 带 system_prompt / tools / trigger_examples。
_Avoid_: 角色、bot、sub-agent

**emotion_calibration**:
情感→动作的**增益曲线**（gain / max / motion），属场景层（可在不改能力的前提下调表现），
与能力注册表的 emotion_mapping（属本体层）是两个东西。
_Avoid_: emotion_mapping（见上）

**inherits**:
场景包的继承字段。子包继承父包，dict 深合并子胜父、list 子包替换、agents 目录并集。
_Avoid_: extends、include

### 离线与部署

**全离线（air-gapped）**:
整个系统断网仍能工作。不依赖任何公网 API——这是隐私与教学现场网络不可靠的双重要求。
_Avoid_: 离线运行、内网部署（内网部署是手段，air-gapped 是要求）

**纯瘦客户端（Thin Client）**:
本体上不跑 LLM/ASR/TTS，只做音频 I/O 与动作执行。因而不增加 GPU 显存预算。
Otto / Reachy / 大亮 / Pepper **四台全部是纯瘦客户端**。
_Avoid_: 边缘推理、端侧模型（恰好相反）

**软急停（softScram）**:
云端可无条件调用的停止工具（如 `self.daliang.stop_all` / `self.pepper.stop_all`）。
任何 Agent 都能调用，是"失联但仍在动"这一最危险形态的兜底。

**overlay（薄改动）**:
对外部第三方项目只做"够用即止"的少量改动，不跟踪其内部演进。
岁悦对 `xiaozhi-esp32-server` 的改造属此类（3 处，见 `brain/mcp/GET_SCENE_OVERLAY_GUIDE.md`），
改动台账记于 `brain/mcp/XIAOZHI_SERVER_PATCHES.md`。
_Avoid_: 魔改、深度定制（那是分叉另一套系统）

**外部本体项目（fork 策略）**:
`firmware-esp32/`（Otto）与 `client-py/`（Reachy）是**独立克隆的嵌套仓库**，
代码在各自 fork 仓库维护，本仓只留 `FORK.md` 作索引；岁悦改造以**纯新增文件**方式进行，
故合并上游零冲突。统一走两阶段：先 zip 验证工具链，再正式 fork 长期维护。
_Avoid_: zip 长期使用（会失去版本信息，上游月更时无法平滑升级）、把上游代码提交进本仓
_Avoid_: 急停（物理急停按钮是另一回事，两者都要有）、急停命令

**geofence**:
禁止或限制机器人进入的空间区域。大亮用 `region` 虚拟墙；Pepper 无原生虚拟墙，
用 ALNavigation 禁区 + 限速近似。
_Avoid_: 电子围栏、禁行区（口语可，文档一律 geofence）

**失联看门狗（Watchdog）**:
网关与大脑心跳中断超过 N 秒 → 自动 `stop_all`。ADR-011 决策 3 定为**不变量**（无论网关部署在哪都必须有）。
_Avoid_: 心跳、超时保护

**MCP-CONTRACT**:
"一个大脑四个身体"的宪法。跨本体工具契约。改契约必须走 ADR。
_Avoid_: 契约文档、接口文档

### Pepper 专有

**NAOqi**:
Pepper 的机器人操作系统（当前固件 2.5.10.7）。官方 `qi` Python SDK **仅支持 Python 2.7**。
_Avoid_: 机器人系统、OS（太泛，会与本体自身 OS 混淆）

**broker**:
NAOqi 的服务代理端点，`tcp://<pepper-ip>:9559`。端侧桥通过它访问 ALxxx 模块。
_Avoid_: 网关（会与岁悦自己的网关混淆）、服务器

**qi-bridge**:
跑在 Windows 上的 Python 2.7 子进程，把云端下发的动作原语派发到 NAOqi proxy，并把音频回传。
只作末端协议桥，**不含任何 LLM/ASR/TTS**。
_Avoid_: naoqi_bridge（那是目录名）、桥接层（泛）

**主网关（Gateway）**:
`suiyue-pepper`，Python 3.13 主进程。扮演小智 client 连云端 WS，同时经**本地 TCP
（127.0.0.1:9560）JSON 行协议**连 qi-bridge。
_Avoid_: 云端网关、bridge（那是 qi-bridge）

**纯 qi 路径**:
不引入 ROS，纯用 `qi` SDK + `ALMotion.moveTo` 实现移动。培训文档的导航章走的是
ROS 路线，本项目**主动不采用**，ALNavigation 拓扑导航仅作可选降级。
_Avoid_: SLAM 导航（Pepper 不是 SLAM）、ROS 导航
