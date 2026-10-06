"""X3 上游接线：给 connection.py 的 _init_prompt_enhancement 打最小补丁。

改动只有 2 处、共约 8 行（overlay 纪律：可一键回滚）：
  1. `_init_prompt_enhancement` 里，把 `self.config["prompt"]` 换成
     经场景注入器处理后的 base prompt。
  2. 文件顶部 import 段加suiyue_scene 导入（带 try/except 兜底，
     缺文件时上游行为完全不变）。

执行前自动备份 connection.py -> connection.py.suiyue.bak
"""
from __future__ import annotations

import io
import os
import shutil
import sys

SRV = (r"D:\WorkBuddy\桌面陪伴机器人\xiaozhi-esp32-server-0.9.7"
       r"\main\xiaozhi-server")
CONN = os.path.join(SRV, "core", "connection.py")

# 1) 顶部 import 锚点（在 from config 之前插入）
IMPORT_ANCHOR = "from config.logger import setup_logging"
IMPORT_NEW = (
    "# ==== suiYue overlay (X3) ====\n"
    "try:  # overlay 缺失时上游行为不变\n"
    "    from suiyue_scene import inject_scene_into_prompt, build_base_prompt\n"
    "except Exception:  # pragma: no cover\n"
    "    inject_scene_into_prompt = None\n"
    "    build_base_prompt = None\n"
    "# ==== end suiYue overlay ====\n"
)

# 2) _init_prompt_enhancement 里的调用替换
OLD_CALL = """        enhanced_prompt = self.prompt_manager.build_enhanced_prompt(
            self.config["prompt"],
            self.device_id,
            self.client_ip,
            emoji_enabled=(self.features or {}).get("emoji", True),
        )"""
NEW_CALL = """        # ==== suiYue overlay (X3) ====
        base_prompt = self.config["prompt"]
        if inject_scene_into_prompt is not None:
            try:
                scene_text = inject_scene_into_prompt(
                    self.config, self.device_id, self.logger
                )
                if scene_text:
                    base_prompt = build_base_prompt(base_prompt, scene_text)
            except Exception as _suiyue_err:  # overlay 永不影响会话
                self.logger.bind(tag=TAG).warning(
                    f"[suiyue] 场景包注入跳过: {_suiyue_err}"
                )
        # ==== end suiYue overlay ====
        enhanced_prompt = self.prompt_manager.build_enhanced_prompt(
            base_prompt,
            self.device_id,
            self.client_ip,
            emoji_enabled=(self.features or {}).get("emoji", True),
        )"""


def main() -> int:
    if not os.path.isfile(CONN):
        print("找不到 connection.py:", CONN)
        return 1

    with io.open(CONN, encoding="utf-8") as fh:
        text = fh.read()

    if "suiYue overlay (X3)" in text:
        print("X3 补丁已存在，跳过（幂等）")
        return 0

    bak = CONN + ".suiyue.bak"
    if not os.path.exists(bak):
        shutil.copy2(CONN, bak)
        print("已备份 ->", os.path.basename(bak))

    # --- 补丁 1：import ---
    if IMPORT_ANCHOR not in text:
        print("!! 找不到 import 锚点:", IMPORT_ANCHOR)
        return 1
    text = text.replace(IMPORT_ANCHOR, IMPORT_NEW + IMPORT_ANCHOR, 1)

    # --- 补丁 2：_init_prompt_enhancement ---
    if OLD_CALL not in text:
        print("!! 找不到 build_enhanced_prompt 调用锚点")
        return 1
    text = text.replace(OLD_CALL, NEW_CALL, 1)

    with io.open(CONN, "w", encoding="utf-8") as fh:
        fh.write(text)
    print("X3 补丁已应用（2 处）")
    print("回滚：把 connection.py.suiyue.bak 覆盖回 connection.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
