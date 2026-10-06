"""overlay/：岁悦对外部 xiaozhi-esp32-server 的薄改动（overlay）。

纪律见 `brain/mcp/XIAOZHI_SERVER_PATCHES.md`：
- `suiyue_scene.py` 是**本仓维护**的注入器，部署时复制到 server 的 `core/` 下。
- 应用到 server 源码用 `tools/apply_overlay_x1x2.py` 与 `tools/apply_overlay_x3.py`。

作为包存在是为了让 `python -m unittest discover` 能发现 test_suiyue_scene.py
（无 __init__.py 的目录会被 discover 跳过 —— 与 e2e/ 同理）。
"""
