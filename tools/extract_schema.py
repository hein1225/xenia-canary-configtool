#!/usr/bin/env python3
"""从 xenia-canary.config.toml 提取结构化设置清单。

输出的每条记录包含：
  section / key / value_raw / value_type / comment(完整原文说明) / line_no

保留说明原文，后续由 translate 层生成中文/英文呈现。
"""
import json
import re
import sys
from pathlib import Path

SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
# key = value  # comment
KV_RE = re.compile(
    r'^\s*(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>"(?:[^"\\]|\\.)*"|true|false|-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?|)'
    r"\s*(?:#(?P<comment>.*))?$"
)
# 仅注释行（续行说明）
COMMENT_ONLY_RE = re.compile(r"^\s*#(?P<comment>.*)$")


def detect_type(raw: str) -> str:
    s = raw.strip()
    if s.startswith('"') and s.endswith('"'):
        return "string"
    if s in ("true", "false"):
        return "bool"
    if re.fullmatch(r"-?\d+", s):
        return "int"
    if re.fullmatch(r"-?\d+\.\d+(?:[eE][-+]?\d+)?", s):
        return "float"
    if s == "":
        return "string"
    return "string"


def strip_trailing_ws(s: str) -> str:
    """去掉行尾空白，但保留行首缩进（用于续行注释对齐分析）。"""
    return s.rstrip()


def parse(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    entries = []
    section = ""
    current = None  # 正在收集续行注释的条目

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        if not stripped:
            # 空行结束当前续行块
            current = None
            continue

        m_sec = SECTION_RE.match(line)
        if m_sec:
            section = m_sec.group(1)
            current = None
            continue

        m_comment = COMMENT_ONLY_RE.match(line)
        if m_comment and not KV_RE.match(line):
            text = m_comment.group("comment")
            if current is not None:
                # 续行：按原始缩进还原层级（统一去掉首尾空白，保留层级信息）
                indent = len(line) - len(line.lstrip())
                current["comment_lines"].append((indent, text.rstrip()))
            continue

        m = KV_RE.match(line)
        if m:
            raw_val = m.group("val")
            comment = (m.group("comment") or "").rstrip()
            entry = {
                "section": section,
                "key": m.group("key"),
                "value_raw": raw_val,
                "value_type": detect_type(raw_val),
                "inline_comment": comment.strip(),
                "comment_lines": [],
                "line_no": idx,
            }
            entries.append(entry)
            current = entry
            continue

        # 无法识别的行：记录下来便于人工核查
        print(f"[WARN] 未识别行 {idx}: {line!r}", file=sys.stderr)

    return entries


def build_comment(entry) -> str:
    """把首行说明与续行说明合并为完整文本，保留相对缩进层级。"""
    parts = []
    if entry["inline_comment"]:
        parts.append(entry["inline_comment"])
    base_indent = None
    for indent, text in entry["comment_lines"]:
        if base_indent is None:
            base_indent = indent
        rel = max(0, indent - base_indent + 2)
        parts.append(" " * rel + text.strip())
    return "\n".join(parts).rstrip()


def main():
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    entries = parse(src)

    for e in entries:
        e["comment"] = build_comment(e)
        del e["comment_lines"]
        del e["inline_comment"]

    groups = {}
    for e in entries:
        groups.setdefault(e["section"], []).append(e["key"])

    result = {
        "source": src.name,
        "total": len(entries),
        "sections": groups,
        "entries": entries,
    }
    out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"条目总数: {len(entries)}")
    for sec, keys in groups.items():
        print(f"  [{sec}] {len(keys)} 项")
    types = {}
    for e in entries:
        types[e["value_type"]] = types.get(e["value_type"], 0) + 1
    print("类型分布:", types)
    no_comment = [e["key"] for e in entries if not e["comment"]]
    print(f"无说明条目: {len(no_comment)} {no_comment}")


if __name__ == "__main__":
    main()
