#!/usr/bin/env python3
"""生成 src/data/names_zh.json —— 列表「简要说明」列用的中文名。

名称来源是 tools/names_zh.py 中逐条撰写的映射（人工校订，非机械截取）。
本脚本负责：校验与 schema.json 完全对齐 → 写出数据文件。

机械提炼（截首句）已被证明不可用：说明文本多为完整句子，
截出来是「对非开发者无用」「如果遇到未实现的 PowerPC 指令」这类半截句子。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from names_zh import NAMES  # noqa: E402

DATA = ROOT / "src" / "data"


def main() -> int:
    schema = json.loads((DATA / "schema.json").read_text(encoding="utf-8"))
    keys = [e["key"] for e in schema.get("entries", [])]

    missing = [k for k in keys if k not in NAMES]
    extra = [k for k in NAMES if k not in set(keys)]
    if missing or extra:
        print(f"✗ 与 schema 不一致：缺 {len(missing)} 项 {missing[:8]}，"
              f"多 {len(extra)} 项 {extra[:8]}", file=sys.stderr)
        return 1

    out = {k: NAMES[k] for k in keys}
    dest = DATA / "names_zh.json"
    dest.write_text(
        json.dumps(out, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    lens = sorted(len(v) for v in out.values())
    print(f"✓ 写入 {dest} —— {len(out)} 条")
    print(f"  名称长度：最短 {lens[0]}，中位 {lens[len(lens) // 2]}，最长 {lens[-1]}")
    longest = max(out.items(), key=lambda kv: len(kv[1]))
    print(f"  最长名称：{longest[0]} = {longest[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
