#!/usr/bin/env python3
"""保留结构的最小 TOML 编辑器。

设计目标（区别于 tomllib / tomli_w 的重写式方案）：
  * 只改动被编辑的那个 key 的那一行，其余字节原样保留
  * 新增 key 时按字母序插入到所属 section 内，顺手补一个空行分隔
  * 保留原有注释、对齐空格、空行分布

这样用户拿 ConfigTool 改过的 config.toml，仍能与 xenia 官方版本 diff 出干净结果。
"""
from __future__ import annotations

import re
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path

SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
KV_RE = re.compile(
    r"^(?P<lead>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?P<eq>\s*=\s*)"
    r"(?P<val>\"(?:[^\"\\]|\\.)*\"|[^#\n]*?)"
    r"(?P<tail>\s*)(?:#(?P<comment>.*))?$"
)


@dataclass
class TomlDoc:
    """一份 config.toml 的内存表示，保留行级结构。"""

    path: Path | None = None
    lines: list[str] = field(default_factory=list)
    # key -> (section, line_index, value_raw, key_col, val_col, comment)
    index: dict[str, tuple] = field(default_factory=dict)
    section_order: list[str] = field(default_factory=list)
    section_first_line: dict[str, int] = field(default_factory=dict)
    section_last_line: dict[str, int] = field(default_factory=dict)
    raw_text: str = ""
    trailing_newline: bool = True

    # ---------- 读取 ----------

    @classmethod
    def load(cls, path: str | Path) -> "TomlDoc":
        p = Path(path)
        text = p.read_text(encoding="utf-8")
        doc = cls(path=p)
        doc.raw_text = text
        doc.trailing_newline = text.endswith("\n")
        doc.lines = text.splitlines()
        doc._reindex()
        return doc

    def _reindex(self) -> None:
        self.index.clear()
        self.section_order.clear()
        self.section_first_line.clear()
        self.section_last_line.clear()

        section = ""
        for i, line in enumerate(self.lines):
            s = line.strip()
            if not s:
                continue
            m = SECTION_RE.match(line)
            if m:
                section = m.group(1)
                if section not in self.section_order:
                    self.section_order.append(section)
                self.section_first_line[section] = i
                self.section_last_line[section] = i
                continue
            if s.startswith("#"):
                continue
            m = KV_RE.match(line)
            if not m:
                continue
            key = m.group("key")
            val_raw = m.group("val").rstrip()
            key_col = len(m.group("lead"))
            val_col = line.index(m.group("val"))
            self.index[key] = (
                section,
                i,
                val_raw,
                key_col,
                val_col,
                m.group("comment"),
            )
            if section:
                self.section_last_line[section] = i

    # ---------- 查询 ----------

    def get(self, key: str) -> str | None:
        rec = self.index.get(key)
        return rec[2] if rec else None

    def get_section(self, key: str) -> str | None:
        rec = self.index.get(key)
        return rec[0] if rec else None

    def keys(self) -> list[str]:
        return list(self.index.keys())

    # ---------- 序列化值 ----------

    @staticmethod
    def format_value(value, vtype: str) -> str:
        """把 Python 值按类型序列化为 TOML 字面量。"""
        if vtype == "bool":
            return "true" if value else "false"
        if vtype == "int":
            if isinstance(value, str):
                value = value.strip()
                return str(int(value, 0)) if value else "0"
            return str(int(value))
        if vtype == "float":
            f = float(value)
            # 保留可读的浮点表示，去掉多余尾零
            s = repr(f)
            return s
        # string：统一加双引号并转义
        s = "" if value is None else str(value)
        s = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{s}"'

    # ---------- 写入（内存中） ----------

    def set(self, key: str, value, vtype: str) -> bool:
        """修改一个 key 的值。返回 True 表示发生了变化。

        只重写该行的 value 片段，保留 key 列对齐与行尾注释。
        """
        new_val = self.format_value(value, vtype)
        rec = self.index.get(key)
        if rec is None:
            return False
        _, i, old_val, key_col, _val_col, comment = rec
        if old_val == new_val:
            return False

        line = self.lines[i]
        m = KV_RE.match(line)
        if not m:
            return False

        lead = m.group("lead")
        k = m.group("key")
        eq = m.group("eq")
        tail = m.group("tail")

        # 重新计算对齐：尽量维持原有 value 结束列位置
        old_end = line.index(m.group("val")) + len(m.group("val"))
        prefix_len = len(lead) + len(k) + len(eq)
        new_line = f"{lead}{k}{eq}{new_val}"
        if comment is not None:
            # 保持原来的 value->comment 间距风格（原文件用制表符分隔）
            gap = old_end - (line.index(m.group("val")) + len(m.group("val")))
            min_gap = 1
            pad = max(min_gap, tail and len(tail) or min_gap)
            # 原文常见：值后跟若干空格再 tab 再 #
            new_line += " " * max(1, pad) + " #" + comment
        self.lines[i] = new_line
        self.index[key] = (rec[0], i, new_val, key_col, prefix_len, comment)
        return True

    def add(self, section: str, key: str, value, vtype: str, comment_line: str = "") -> None:
        """在指定 section 内按字母序插入新 key。"""
        new_val = self.format_value(value, vtype)
        if key in self.index:
            self.set(key, value, vtype)
            return

        insert_at = None
        if section in self.section_first_line:
            first = self.section_first_line[section]
            last = self.section_last_line[section]
            insert_at = last + 1
            for i in range(first, last + 1):
                m = KV_RE.match(self.lines[i])
                if m and m.group("key") > key:
                    insert_at = i
                    break
            # 若尾部是续行注释块，避免插到注释中间：往回找到最后一个 key 行
            while insert_at - 1 > first:
                prev = self.lines[insert_at - 1].strip()
                if prev.startswith("#"):
                    insert_at -= 1
                else:
                    break
            # 插到注释块之前
            probe = insert_at
            while probe < last + 1 and self.lines[probe].strip().startswith("#"):
                probe += 1
            if probe <= last:
                insert_at = min(insert_at, probe)
        else:
            # section 不存在：追加到文件末尾
            self.lines.append("")
            self.lines.append(f"[{section}]")
            insert_at = len(self.lines)

        pad = max(1, 51 - len(key) - len(new_val) - 3)
        line = f'{key} = {new_val}{" " * pad}# {comment_line}'.rstrip()
        self.lines.insert(insert_at, line)
        self._reindex()

    # ---------- 落盘 ----------

    def to_text(self) -> str:
        out = "\n".join(self.lines)
        if self.trailing_newline:
            out += "\n"
        return out

    def save(self, path: str | Path | None = None, backup: bool = True) -> Path | None:
        """写回文件。backup=True 时先生成带时间戳的 .bak 备份。

        返回备份文件路径（未备份时为 None）。
        """
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ValueError("未指定保存路径")

        backup_path = None
        if backup and target.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup_path = target.with_name(f"{target.name}.{stamp}.bak")
            # 避免同秒重复覆盖
            n = 1
            while backup_path.exists():
                backup_path = target.with_name(f"{target.name}.{stamp}-{n}.bak")
                n += 1
            shutil.copy2(target, backup_path)

        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(self.to_text(), encoding="utf-8")
        tmp.replace(target)
        return backup_path

    # ---------- 校验 ----------

    def validate(self) -> list[str]:
        """用标准库 tomllib 校验渲染结果是否仍是合法 TOML。"""
        import tomllib

        try:
            tomllib.loads(self.to_text())
            return []
        except Exception as exc:  # noqa: BLE001
            return [str(exc)]
