#!/usr/bin/env python3
"""把原始 schema 加工为程序使用的 data/schema.json。

在提取的基础上补充：
  * choices：从说明的 `Use: [...]` 里解析出的枚举可选项 → 界面下拉框
  * default：xenia 官方默认值（取自参考配置文件）
  * range：从说明里解析出的数值范围提示
  * advanced：是否属于开发者/调试向选项
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

USE_RE = re.compile(r"Use:\s*\[([^\]]+)\]")
# 兼容 "CPU backend [any, x64]" 这类未使用 "Use:" 前缀的枚举写法
BARE_ENUM_RE = re.compile(r"(?:backend|system|mode|version|path)\s*\[([a-z0-9_,\s\-]+)\]", re.I)
RANGE_RE = re.compile(r"[Rr]ange\s+([-\d.]+)\s*[-~到]\s*([-\d.]+)")
BOOL_HINT_RE = re.compile(r"\b(true|false|0\s*[-–]\s*|0\s*-\s*)")

ADVANCED_SECTIONS = {"CPU", "GPU.Debug", "Logging", "Memory", "x64", "Kernel", "Config", "Win32"}
ADVANCED_KEYS = {
    "debug", "break_on_start", "break_on_instruction", "break_condition_gpr",
    "break_condition_op", "break_condition_truncate", "break_condition_value",
    "break_on_unimplemented_instructions", "d3d12_debug", "d3d12_break_on_error",
    "d3d12_break_on_warning", "vulkan_validation", "imgui_debug", "show_profiler",
    "profiler_dpi_scaling", "debug_symbol_loader", "trace_gpu_stream",
    "trace_function_coverage", "trace_function_data", "trace_function_references",
    "trace_functions", "disassemble_functions", "store_all_context_values",
    "validate_hir", "dump_shaders", "dxbc_source_map", "disassemble_pm4",
    "enable_console", "log_to_debugprint", "kernel_pix", "staging_mode",
    "kernel_cert_monitor", "kernel_debug_monitor",
}


def parse_choices(desc: str) -> list[str]:
    """从说明中解析枚举可选项。"""
    m = USE_RE.search(desc)
    if not m:
        m = BARE_ENUM_RE.search(desc)
    if not m:
        return []
    raw = m.group(1)
    items = [x.strip() for x in raw.split(",")]
    out = []
    for it in items:
        it = it.strip().strip("'\"")
        if not it:
            continue
        # 过滤说明性文字（如 "or any value not listed here"）
        if " " in it:
            continue
        out.append(it)
    return out


def parse_range(desc: str, vtype: str) -> list | None:
    m = RANGE_RE.search(desc)
    if m:
        try:
            return [float(m.group(1)), float(m.group(2))]
        except ValueError:
            return None
    # 常见模式：[0.0-1.0] / [1-255] / [0, 3]
    m2 = re.search(r"\[(-?\d+(?:\.\d+)?)\s*[-–,]\s*(-?\d+(?:\.\d+)?)\]", desc)
    if m2:
        try:
            return [float(m2.group(1)), float(m2.group(2))]
        except ValueError:
            return None
    return None


def main() -> int:
    raw_path = Path(sys.argv[1])
    ref_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3])

    raw = json.loads(raw_path.read_text(encoding="utf-8"))

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from toml_edit import TomlDoc  # noqa: E402

    ref = TomlDoc.load(ref_path)

    entries = []
    choice_count = 0
    for e in raw["entries"]:
        desc = e["comment"]
        vtype = e["value_type"]
        choices = parse_choices(desc) if vtype == "string" else []
        if choices:
            choice_count += 1
        item = {
            "key": e["key"],
            "section": e["section"],
            "value_type": vtype,
            "default": e["value_raw"],
            "comment": desc,
            "choices": choices,
            "range": parse_range(desc, vtype),
            "advanced": e["section"] in ADVANCED_SECTIONS or e["key"] in ADVANCED_KEYS,
            "line_no": e["line_no"],
        }
        entries.append(item)

    # 一致性校验：raw 提取的 key 必须与 TOML 引擎解析的完全一致
    engine_keys = set(ref.keys())
    schema_keys = {e["key"] for e in entries}
    if engine_keys != schema_keys:
        print(f"[ERROR] key 集合不一致: 差集 {engine_keys ^ schema_keys}", file=sys.stderr)
        return 1
    # 默认值一致性
    mismatched = [e["key"] for e in entries if ref.get(e["key"]) != e["default"]]
    if mismatched:
        print(f"[ERROR] 默认值不一致: {mismatched}", file=sys.stderr)
        return 1

    result = {
        "source": raw["source"],
        "total": len(entries),
        "sections": raw["sections"],
        "entries": entries,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"✓ 条目 {len(entries)}，分组 {len(raw['sections'])}")
    print(f"✓ 带枚举可选项的条目: {choice_count}")
    print(f"✓ 带数值范围提示: {sum(1 for e in entries if e['range'])}")
    print(f"✓ 开发者选项: {sum(1 for e in entries if e['advanced'])}")
    print("✓ key 集合与默认值均与 TOML 引擎一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
