"""CI/本地通用：校验 suiyue 下所有 YAML 可被 safe_load 解析。

背景：场景包历史上出现过两类真实事故——
  1. elder_cn_v1/persona.yaml 里 `concerned:{...}` 缺空格（PyYAML 要求 `key: {`）；
  2. kids_v1/scene.yaml 用了 `>` 折叠标量但同行跟了文字（非法）。
两者都不会在纯语法检查里报错，只有真正解析时才暴露，故固化为可执行门禁。

用法：
    python suiyue/tools/lint_yaml.py
退出码：0 = 全部通过；1 = 有文件解析失败。
"""
from __future__ import annotations

import glob
import os
import sys

import yaml

# 仓库内根目录（suiyue/）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    files = sorted(glob.glob(os.path.join(_ROOT, "**", "*.yaml"), recursive=True))
    files = [f for f in files if "__pycache__" not in f]

    bad = 0
    for path in files:
        rel = os.path.relpath(path, _ROOT)
        try:
            with open(path, encoding="utf-8") as fh:
                yaml.safe_load(fh)
            print("OK   %s" % rel)
        except Exception as exc:
            print("FAIL %s -> %s" % (rel, exc))
            bad += 1

    print("\n共 %d 个 YAML，失败 %d" % (len(files), bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
