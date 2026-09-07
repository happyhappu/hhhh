"""brain/core：云端统一意图分发中枢（"一个大脑三个身体"的云端侧实现）。

- capability.py  加载各本体能力注册表（capabilities/<model>.yaml）
- provider.py    本体提供方抽象：StaticProvider（模拟固件）/ DaliangProvider（实时底盘）
- brain.py       SuiyueBrain：按设备号路由 emote 意图到正确本体
"""
