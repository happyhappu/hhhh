"""大亮本体在云端大脑侧的编排 Provider。

把 MCP-CONTRACT §1 的情感意图翻译成 self.daliang.* 底盘命令，并把底盘事件
桥接成对话上下文。与具体传输无关，可作为 xiaozhi-esp32-server fork 的 MCP provider 挂载。
"""
from .orchestrator import DaliangOrchestrator, TOOLS

__all__ = ["DaliangOrchestrator", "TOOLS"]
