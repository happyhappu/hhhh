"""brain/mcp：把 SuiyueBrain 暴露为标准 MCP server 的子包。

对外暴露 SuiyueMCPServer（传输无关的核心）。stdio 启动入口见 __main__。
"""
from .server import SuiyueMCPServer

__all__ = ["SuiyueMCPServer"]
