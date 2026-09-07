"""MCP stdio 传输入口（JSON-RPC 2.0，换行分隔）。

用法（在 suiyue/ 根目录，venv 激活）：
    python -m brain.mcp --config brain/mcp/config.yaml

xiaozhi-esp32-server 集成时，把它配成一个 stdio MCP server 即可（见 README.md）。
stdin 用后台线程逐行读取并投喂 asyncio 队列，跨平台（含 Windows）可用。
日志一律走 stderr，不污染 stdout 的 JSON-RPC 流。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import threading

from .server import SuiyueMCPServer
from .config import load_config

SERVER_INFO = {"name": "suiyue-brain", "version": "0.1.0"}
PROTOCOL_VERSION = "2024-11-05"  # 客户端 initialize 时若带 protocolVersion 则回显其版本


async def _stdio_loop(server: SuiyueMCPServer) -> None:
    loop = asyncio.get_event_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _reader() -> None:
        # 后台线程：从 stdin 逐行读取，投喂到事件循环队列
        for line in sys.stdin:
            loop.call_soon_threadsafe(queue.put_nowait, line)

    threading.Thread(target=_reader, daemon=True).start()

    def _send(obj: dict) -> None:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    while True:
        line = await queue.get()
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = msg.get("method")
        mid = msg.get("id")
        params = msg.get("params", {}) or {}

        if method == "initialize":
            pv = params.get("protocolVersion", PROTOCOL_VERSION)
            _send(
                {
                    "jsonrpc": "2.0",
                    "id": mid,
                    "result": {
                        "protocolVersion": pv,
                        "capabilities": {"tools": {}},
                        "serverInfo": SERVER_INFO,
                    },
                }
            )
        elif method == "notifications/initialized":
            continue  # 通知类，无需响应
        elif method == "tools/list":
            tools = await server.list_tools()
            _send({"jsonrpc": "2.0", "id": mid, "result": {"tools": tools}})
        elif method == "tools/call":
            name = params.get("name", "")
            arguments = params.get("arguments", {}) or {}
            result = await server.call_tool(name, arguments)
            _send({"jsonrpc": "2.0", "id": mid, "result": result})
        elif method == "ping":
            _send({"jsonrpc": "2.0", "id": mid, "result": {}})
        else:
            if mid is not None:
                _send(
                    {
                        "jsonrpc": "2.0",
                        "id": mid,
                        "error": {"code": -32601, "message": f"method not found: {method}"},
                    }
                )


async def main() -> None:
    ap = argparse.ArgumentParser(description="岁悦大脑 MCP server（stdio）")
    ap.add_argument("--config", default=None, help="MCP 配置文件路径（默认 brain/mcp/config.yaml）")
    ap.add_argument("--log", default=None, help="日志文件路径（默认 stderr）")
    args = ap.parse_args()

    logging.basicConfig(
        filename=args.log,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    cfg = load_config(args.config)
    server = SuiyueMCPServer()
    await server.setup(cfg)
    try:
        await _stdio_loop(server)
    finally:
        await server.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
