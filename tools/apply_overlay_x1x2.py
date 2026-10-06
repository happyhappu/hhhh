"""X1 + X2落地：给 v0.9.7 源码写入岁悦 device_id 与大脑 MCP 注册。

改动点（overlay 纪律：最小侵入，可一键回滚）：
  X1 → main/xiaozhi-server/config.yaml新增 suiyue 段
  X2 → main/xiaozhi-server/mcp_server_settings.json 注册大脑 MCP server（stdio）

执行前会自动备份原文件（*.suiyue.bak）。
"""
from __future__ import annotations

import io
import json
import os
import shutil
import sys

SRV = (r"D:\WorkBuddy\桌面陪伴机器人\xiaozhi-esp32-server-0.9.7"
       r"\main\xiaozhi-server")

DEVICE_ID = "pepper-01"          # 必须与suiyue/brain/mcp/config.yaml 字面一致
BRAIN_REPO = r"D:\WorkBuddy\桌面陪伴机器人\suiyue"   # 部署到 4090 后改成 /opt/suiyue


def backup(path: str) -> None:
    bak = path + ".suiyue.bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print("  已备份 ->", os.path.basename(bak))


def do_x1() -> None:
    print("\n" + "=" * 66)
    print("X1 · config.yaml 新增 suiyue.device_id")
    print("=" * 66)
    p = os.path.join(SRV, "config.yaml")
    if not os.path.isfile(p):
        print("  配置文件不存在:", p)
        return
    with io.open(p, encoding="utf-8") as fh:
        text = fh.read()

    if "suiyue:" in text:
        print("  已存在 suiyue 段，跳过")
        return

    backup(p)
    block = (
        "\n# ==== 岁悦 overlay (X1) ====\n"
        "# 声明本机代表的本体 id；会话开始调大脑 MCP get_scene 时使用。\n"
        "# 必须与 suiyue/brain/mcp/config.yaml 里注册的 device_id 字面一致。\n"
        "suiyue:\n"
        "  device_id: %s\n"
        "  brain_mcp_enabled: true\n"
        "# ==== end suiyue overlay ====\n"
    ) % DEVICE_ID
    with io.open(p, "w", encoding="utf-8") as fh:
        fh.write(text + block)
    print("  已追加 suiyue 段（文件末尾）")
    print("  device_id =", DEVICE_ID)


def do_x2() -> None:
    print("\n" + "=" * 66)
    print("X2 · mcp_server_settings.json 注册大脑 MCP server（stdio）")
    print("=" * 66)
    p = os.path.join(SRV, "mcp_server_settings.json")
    if not os.path.isfile(p):
        print("  注册文件不存在:", p)
        return
    backup(p)
    with io.open(p, encoding="utf-8") as fh:
        data = json.load(fh)

    servers = data.setdefault("mcpServers", {})
    if "suiyue-brain" in servers:
        print("  已注册 suiYue-brain，跳过")
        return

    servers["suiyue-brain"] = {
        "command": "python3",
        "args": ["-m", "brain.mcp", "--config",
                 os.path.join(BRAIN_REPO, "brain", "mcp", "config.yaml").replace("\\", "/")],
        "des": "岁悦大脑 MCP server（stdio）。提供 self.suiyue.get_scene / emote / list_devices 等工具。",
    }
    with io.open(p, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    print("  已注册 mcpServers['suiyue-brain']")
    print("  传输: stdio（上游原生支持，另可选 sse / streamable-http）")
    print("  注意: args 里的路径需按部署机实际情况调整")


def main() -> int:
    print("X1 + X2 落地中...")
    print("目标目录:", SRV)
    do_x1()
    do_x2()
    print("\n完成。回滚方式：用 *.suiyue.bak 覆盖回原文件。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
