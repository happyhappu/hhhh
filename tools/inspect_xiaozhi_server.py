"""xiaozhi-esp32-server 下载版核查工具（只读）。

用途：下载/升级 server 后，一次跑完三件事——
  1. 结构完整性（是否是完整的 server 源码树）
  2. 版本判定（能否确定 tag；能否看出是 main 分支）
  3. overlay 落点定位（X1 config.yaml / X2 mcp_manager / X3 prompt_manager）

用法：
    python suiyue/tools/inspect_xiaozhi_server.py [server目录]

默认目录：D:\\WorkBuddy\\桌面陪伴机器人\\xiaozhi-esp32-server
"""
from __future__ import annotations

import io
import os
import re
import sys

DEFAULT_BASE = r"D:\WorkBuddy\桌面陪伴机器人\xiaozhi-esp32-server"
REL_SERVER = os.path.join("main", "xiaozhi-server")

STRUCT_MARKERS = [
    "main", "docs", "LICENSE", "README.md", "docker-setup.sh",
    "Dockerfile-server", "Makefile",
]
INNER_MARKERS = [
    "app.py", "config.yaml", "core", "docker-compose.yml",
    "requirements.txt", "mcp_server_settings.json", "agent-base-prompt.txt",
]

# overlay 落点：相对 xiaozhi-server 目录
OVERLAY_POINTS = [
    ("X1", os.path.join("config.yaml"), r"mcp_endpoint|MCP接入点",
     "新增 suiyue.device_id（与大脑 config.yaml 字面一致）"),
    ("X2", os.path.join("core", "providers", "tools", "server_mcp", "mcp_manager.py"),
     r"def load_config|def initialize_servers|def _init_server",
     "上游已原生支持 stdio/sse/streamable-http；句柄在 self.clients[name]"),
    ("X3", os.path.join("core", "utils", "prompt_manager.py"),
     r"def build_enhanced_prompt|def _load_base_template",
     "Jinja2 Template(...).render(base_prompt=...)；模板 agent-base-prompt.txt"),
]


def read_lines(path: str) -> list:
    try:
        with io.open(path, encoding="utf-8", errors="ignore") as fh:
            return fh.read().splitlines()
    except Exception:
        return []


def find_server_root(base: str) -> str:
    """在 base 及其一层子目录里定位含main/xiaozhi-server 的真实 server 根。"""
    cands = [base]
    try:
        for n in os.listdir(base):
            p = os.path.join(base, n)
            if os.path.isdir(p):
                cands.append(p)
    except Exception:
        pass
    for c in cands:
        if os.path.isfile(os.path.join(c, REL_SERVER, "app.py")):
            return c
    return ""


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE
    print("检查目录:", base)
    if not os.path.isdir(base):
        print("  目录不存在。请传实际路径：python suiyue/tools/inspect_xiaozhi_server.py <路径>")
        return 1

    root = find_server_root(base)
    if not root:
        print("  未找到 main/xiaozhi-server/app.py —— 可能不是完整 server 源码树")
        print("  顶层内容:", os.listdir(base)[:20])
        return 1

    print("  server 根定位成功:", root)
    if os.path.normcase(root) != os.path.normcase(base):
        print("  ⚠️ 注意：真实源码在子目录里（解压套了一层）")
    srv = os.path.join(root, REL_SERVER)

    print("\n=== 1) 结构完整性 ===")
    ok_struct = sum(1 for m in STRUCT_MARKERS if os.path.exists(os.path.join(root, m)))
    print("  外层标志: %d/%d" % (ok_struct, len(STRUCT_MARKERS)))
    ok_inner = sum(1 for m in INNER_MARKERS if os.path.exists(os.path.join(srv, m)))
    print("  内层标志: %d/%d" % (ok_inner, len(INNER_MARKERS)))
    if ok_inner < len(INNER_MARKERS):
        print("  -> 内层缺失:", [m for m in INNER_MARKERS
                                 if not os.path.exists(os.path.join(srv, m))])

    print("\n=== 2) 版本判定 ===")
    has_git = os.path.isdir(os.path.join(root, ".git"))
    name_ver = re.search(r"(\d+\.\d+\.\d+)", os.path.basename(base))
    print("  含 .git:", has_git)
    print("  目录名含版本号:", name_ver.group(1) if name_ver else "无")
    if has_git:
        print("  -> 精确取 tag: git -C \"%s\" describe --tags" % base)
    elif name_ver:
        print("  -> 疑似 Release zip，版本 =", name_ver.group(1))
    else:
        print("  -> ⚠️ 无 .git 且目录名无版本号 = **main 分支 zip**")
        print("     源码内通常无 version 字段，无法复现版本。")
        print("     建议：删除后从 Releases 下tag 版（如 v0.9.7），目录名即版本。")
    for rel in ("Makefile", "README.md", "docker-setup.sh"):
        for l in read_lines(os.path.join(root, rel))[:200]:
            m = re.search(r"v?(0\.9\.[0-9]+)", l)
            if m:
                print("  %s 提及版本: %s" % (rel, m.group(1)))
                break

    print("\n=== 3) overlay 落点定位 ===")
    for tag, rel, pattern, note in OVERLAY_POINTS:
        p = os.path.join(srv, rel)
        if not os.path.isfile(p):
            print("  [%s] %s -> 文件缺失" % (tag, rel))
            continue
        lines = read_lines(p)
        print("  [%s] %s（%d 行）" % (tag, rel, len(lines)))
        for i, l in enumerate(lines, 1):
            if re.search(pattern, l):
                print("        %4d| %s" % (i, l.strip()[:96]))
        print("        意图:", note)

    print("\n=== 4) MCP 注册位（把大脑 MCP 放这里）===")
    mcp_json = os.path.join(srv, "mcp_server_settings.json")
    if os.path.isfile(mcp_json):
        print("  ", mcp_json)
        print("  -> 把 suiYue 大脑 MCP 条目加进 mcpServers（stdio 传输）")
        print("     样例参考: suiyue/brain/mcp/xiaozhi-mcp-settings.example.json")
    else:
        print("  未找到 mcp_server_settings.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
