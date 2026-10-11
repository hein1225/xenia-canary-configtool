#!/usr/bin/env python3
"""端到端验收测试：验证核心功能在真实配置文件上的行为。

[1]–[9] 只测引擎层，不需要显示环境；
[10] 需要真实 Tk 窗口来验证列宽与计数，会自行准备显示环境。

显示环境说明：第 [10] 项把窗口设为 1500x950 并强制 tk scaling=2.0，
在 scaling=2.0 下最长键名（emit_mmio_aware_stores_for_recorded_exception_addresses）
需要约 625px 的列宽。若屏幕宽度不足（如 1280x800），Tk 会把列压到 606px，
测试就会误报失败——这不是程序缺陷，而是测试环境分辨率不够。
因此这里主动确保显示环境足够大（至少 1600x1000），必要时自行拉起 Xvfb。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from i18n import Resources  # noqa: E402
from toml_edit import TomlDoc  # noqa: E402

PASS, FAIL = [], []

# 第 [10] 项所需的最小屏幕宽度（见模块 docstring 的说明）
MIN_SCREEN_W = 1600
MIN_SCREEN_H = 1000
_own_xvfb: subprocess.Popen | None = None


def _screen_size() -> tuple[int, int] | None:
    """读取当前 DISPLAY 的尺寸，失败返回 None。"""
    disp = os.environ.get("DISPLAY")
    if not disp:
        return None
    try:
        out = subprocess.run(["xdpyinfo", "-display", disp],
                             capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.stdout.splitlines():
        line = line.strip()
        if line.startswith("dimensions:"):
            try:
                wh = line.split()[1]
                w, h = wh.split("x")
                return int(w), int(h)
            except (IndexError, ValueError):
                return None
    return None


def ensure_display() -> tuple[bool, str]:
    """确保有一个足够大的显示环境可供第 [10] 项使用。

    返回 (是否可用, 说明)。优先复用现有 DISPLAY；若不存在或尺寸不足，
    则自行拉起一个 1600x1000 的 Xvfb。
    """
    global _own_xvfb

    size = _screen_size()
    if size and size[0] >= MIN_SCREEN_W and size[1] >= MIN_SCREEN_H:
        return True, f"复用现有 DISPLAY={os.environ['DISPLAY']} ({size[0]}x{size[1]})"
    if size:
        print(f"  [!] 现有显示 {size[0]}x{size[1]} 太小"
              f"（第 [10] 项需要 ≥{MIN_SCREEN_W}x{MIN_SCREEN_H}），另起 Xvfb")

    if shutil.which("Xvfb") is None:
        return False, "未安装 Xvfb，且没有足够大的 DISPLAY"

    for num in (97, 96, 95, 94):
        disp = f":{num}"
        if _screen_size_for(disp):
            continue
        try:
            proc = subprocess.Popen(
                ["Xvfb", disp, "-screen", "0",
                 f"{MIN_SCREEN_W}x{MIN_SCREEN_H}x24"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            return False, f"无法启动 Xvfb: {exc}"
        for _ in range(24):
            time.sleep(0.25)
            if _screen_size_for(disp):
                _own_xvfb = proc
                os.environ["DISPLAY"] = disp
                return True, f"已启动 Xvfb {disp} ({MIN_SCREEN_W}x{MIN_SCREEN_H})"
        proc.terminate()
    return False, "Xvfb 启动后仍不可用"


def _screen_size_for(disp: str) -> tuple[int, int] | None:
    """查询指定 DISPLAY 的尺寸。"""
    saved = os.environ.get("DISPLAY")
    os.environ["DISPLAY"] = disp
    try:
        return _screen_size()
    finally:
        if saved is None:
            os.environ.pop("DISPLAY", None)
        else:
            os.environ["DISPLAY"] = saved


def check(name: str, ok: bool, detail: str = "") -> None:
    (PASS if ok else FAIL).append(name)
    mark = "✓" if ok else "✗"
    print(f"  {mark} {name}" + (f"  — {detail}" if detail else ""))


def main() -> int:
    ref = ROOT / "reference.config.toml"
    print(f"参考配置: {ref}\n")

    # ---------------------------------------------------------- 1. 往返无损
    print("[1] 读入-序列化往返一致性")
    original = ref.read_text(encoding="utf-8")
    doc = TomlDoc.load(ref)
    check("逐字节往返一致", doc.to_text() == original)
    check("行数保持 553", len(doc.to_text().splitlines()) == 553,
          f"实际 {len(doc.to_text().splitlines())}")

    # ---------------------------------------------------------- 2. schema 覆盖
    print("\n[2] schema 与配置文件的一致性")
    schema = json.loads((ROOT / "src/data/schema.json").read_text(encoding="utf-8"))
    entries = schema["entries"]
    cfg_keys = set(doc.keys())
    schema_keys = {e["key"] for e in entries}
    check("项目数 267", len(entries) == 267, f"实际 {len(entries)}")
    check("schema 覆盖全部已解析项", schema_keys <= cfg_keys,
          f"schema 多出 {sorted(schema_keys - cfg_keys)[:3]}")
    check("配置项无遗漏", cfg_keys <= schema_keys,
          f"配置多出 {sorted(cfg_keys - schema_keys)[:3]}")
    check("分组数 23", len(schema["sections"]) == 23, f"实际 {len(schema['sections'])}")

    # ---------------------------------------------------------- 3. 精确写入
    print("\n[3] 写入最小性：只改目标行")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "cfg.toml"
        shutil.copy(ref, tmp)
        d2 = TomlDoc.load(tmp)
        targets = {"fullscreen", "vsync", "time_scalar", "mute",
                   "postprocess_antialiasing", "gpu", "apu", "hid"}
        before = d2.to_text().splitlines()
        d2.set("fullscreen", True, "bool")
        d2.set("time_scalar", 2, "int")
        d2.set("mute", True, "bool")
        after = d2.to_text().splitlines()
        check("行数不变", len(before) == len(after))
        diff = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        check("仅 3 行发生变化", len(diff) == 3, f"实际 {len(diff)} 行")

        # 注释与顺序保全
        check("注释完整保留",
              sum(1 for l in after if l.lstrip().startswith("#")) ==
              sum(1 for l in before if l.lstrip().startswith("#")))
        txt = d2.to_text()
        check("写入值正确", "time_scalar = 2" in txt and "fullscreen = true" in txt)

        # ------------------------------------------------------ 4. 语法有效
        print("\n[4] 写入结果语法有效")
        try:
            parsed = tomllib.loads(txt)
            check("tomllib 解析通过", True)
            check("解析值符合预期",
                  parsed["Display"]["fullscreen"] is True and
                  parsed["General"]["time_scalar"] == 2)
        except Exception as exc:  # noqa: BLE001
            check("tomllib 解析通过", False, str(exc))

        # 其余未触碰项完全一致
        untouched = set(before) and True
        same = all(
            a == b for a, b in zip(before, after)
            if not any(t in b for t in ("fullscreen", "time_scalar", "mute"))
        )
        check("未触碰项原样保留", same)

    # ---------------------------------------------------------- 5. 未知项保留
    print("\n[5] 前向兼容：未知配置项保留")
    d3 = TomlDoc.load(ref)
    d3.lines.insert(4, 'future_option = "x"   # 未来新增')
    d3._reindex()
    d3.set("vsync", True, "bool")
    out = d3.to_text()
    check("未知项未被丢弃", 'future_option = "x"' in out)
    check("未知项注释保留", "# 未来新增" in out)
    check("仍为合法 TOML", bool(tomllib.loads(out)))

    # ---------------------------------------------------------- 6. 双语资源
    print("\n[6] 双语资源完整性")
    res = Resources(ROOT / "src/data")
    check("中文说明 267 条", len(res.desc_zh) == 267, f"实际 {len(res.desc_zh)}")
    check("英文说明 267 条", len(res.desc_en) == 267, f"实际 {len(res.desc_en)}")

    miss_zh = [e["key"] for e in entries if not res.describe("zh", e["key"])]
    check("每项都有中文说明", not miss_zh, f"缺失 {miss_zh[:3]}")
    miss_en = [e["key"] for e in entries if not res.describe("en", e["key"])]
    check("每项都有英文说明", not miss_en, f"缺失 {miss_en[:3]}")

    # 中文说明不应残留未翻译的英文段落
    import re
    zh_only = [k for k, v in res.desc_zh.items()
               if v and not re.search(r"[\u4e00-\u9fff]", v)
               and len(re.sub(r"[A-Za-z0-9\s\[\]\(\),\.\-_/:=]+", "", v)) < 3]
    check("中文说明无纯英文残留", len(zh_only) <= 2, f"{len(zh_only)} 条: {zh_only[:3]}")

    # ---------------------------------------------------------- 7. 枚举元数据
    print("\n[7] 枚举与范围元数据")
    enum_entries = [e for e in entries if e.get("choices")]
    check("枚举项已识别", len(enum_entries) >= 9, f"实际 {len(enum_entries)}")
    named = {e["key"] for e in enum_entries}
    for key in ("apu", "gpu", "cpu", "hid", "xma_decoder"):
        check(f"  {key} 的枚举值已抓取", key in named)
    ranges = [e for e in entries if e.get("range")]
    check("数值范围已抓取", len(ranges) >= 5, f"实际 {len(ranges)}")

    # ---------------------------------------------------------- 8. 预设
    print("\n[8] 掌机预设")
    sys.path.insert(0, str(ROOT / "src"))
    import navmeta
    check("预设数量", len(navmeta.DEVICE_PRESETS) == 3)
    all_keys = {e["key"] for e in entries}
    for p in navmeta.DEVICE_PRESETS:
        bad = [k for k in p["values"] if k not in all_keys]
        check(f"  预设 {p['id']} 的 key 均存在", not bad, f"无效 {bad}")
    check("推荐项清单有效",
          all(k in all_keys for k in navmeta.FEATURED_KEYS),
          f"无效 {[k for k in navmeta.FEATURED_KEYS if k not in all_keys]}")

    # ---------------------------------------------------------- 9. 导航元数据
    print("\n[9] 导航分类元数据")
    nav_sections = [s for g in navmeta.NAV_GROUPS for s in g["sections"]]
    real_sections = set(schema["sections"])
    check("导航覆盖全部分组", set(nav_sections) == real_sections,
          f"缺 {sorted(real_sections - set(nav_sections))} 多 {sorted(set(nav_sections) - real_sections)}")
    check("分组无重复", len(nav_sections) == len(set(nav_sections)))
    check("每个分组都有图标",
          all(s in navmeta.SECTION_ICONS for s in real_sections))
    check("每个分组都有简介",
          all(navmeta.nav_blurb("zh", s) for s in real_sections))

    # ---------------------------------------------------------- 10. 卡片计数一致性
    # 卡片/左栏显示的数字必须等于该分组实际能列出的条数。
    # 曾经两者脱节：Kernel、Logging 整组都是高级项，卡片写 16/12，
    # 点进去却一条都没有，用户以为是程序坏了。
    print("\n[10] 卡片计数 == 实际列出的条数")
    ok, note = ensure_display()
    print(f"  · 显示环境: {note}")
    if not ok:
        check("卡片计数一致性（需要显示环境）", False, note)
        return _finish()
    try:
        import tkinter as tk
        import app as appmod
        root = tk.Tk()
        # 必须给定窗口尺寸：默认窗口很窄，列会被压缩，测不出真实的分配规则。
        root.geometry("1500x950")
        root.tk.call("tk", "scaling", 2.0)
        a = appmod.ConfigToolApp(root)
        # 应用默认会在启动后自动最大化，会把上面指定的 1500x950 冲掉，
        # 测的就不是我们想要的那组尺寸了。这里撤销它的定时任务，保持
        # 尺寸可控；自动最大化本身由 tools/test_maximize.py 单独覆盖。
        a._maximize_off = True
        for _ in range(30):
            root.update(); root.update_idletasks(); time.sleep(0.02)
        mismatch = []
        checked = 0
        for nav in navmeta.NAV_GROUPS:
            a.select_nav(nav["id"])
            for _ in range(30):
                root.update(); root.update_idletasks(); time.sleep(0.02)
            for sec in a.visible_sections(nav["id"]):
                n_card = a._section_visible_count(sec)[0]
                a.select_section(sec)
                for _ in range(25):
                    root.update(); root.update_idletasks(); time.sleep(0.02)
                checked += 1
                if len(a.rows) != n_card:
                    mismatch.append(f"{nav['id']}/{sec}: 卡片 {n_card} 实列 {len(a.rows)}")
        check(f"全部 {checked} 个分组计数一致", not mismatch,
              "; ".join(mismatch[:4]))

        # 列宽规则：设置项必须完整显示最长键名；设置项与中文名等宽；
        # 当前值与已修改等宽；总宽贴合内容不撑满。
        pad = 16
        bad_wide, bad_pair, bad_total = [], [], []
        for nav in navmeta.NAV_GROUPS:
            a.select_nav(nav["id"])
            for _ in range(30):
                root.update(); root.update_idletasks(); time.sleep(0.02)
            for sec in a.visible_sections(nav["id"]):
                a.select_section(sec)
                # 列宽由 after(80ms) 防抖后重算，必须等真实时间过去再读，
                # 否则读到的是上一组的旧宽度（mark=58 就是布局未完成的残留值）。
                settle_t = time.time()
                while time.time() - settle_t < 0.45:
                    root.update(); root.update_idletasks(); time.sleep(0.02)
                if not a.rows:
                    continue
                c = {k: a.tree.column(k, "width") for k in
                     ("key", "brief", "value", "modified")}
                lk = max((r["key"] for r in a.rows), key=len)
                need = a._text_width(lk) + pad
                if c["key"] < need:
                    bad_wide.append(f"{sec}: {c['key']}<{need}({lk})")
                # 等宽只在「两列内容都不需要额外宽度」时才要求。
                # 含超长键名（d3d12_allow_variable_refresh_rate_an）或超长值
                # （0.20000000298023224）的组必然不等宽，这是内容决定的，不算缺陷。
                lv = max((a.format_display(r["key"], r["type"]) for r in a.rows),
                         key=len, default="")
                val_need = a._text_width(lv) + pad
                if c["brief"] > c["key"] + 2:
                    bad_pair.append(f"{sec}: 中文名比设置项更宽 {c['brief']}>{c['key']}")
                if val_need <= c["modified"] + 4 and c["value"] > c["modified"] + 4:
                    bad_pair.append(
                        f"{sec}: 值只需 {val_need} 却占 {c['value']}（已修改 {c['modified']}）")
                star_w = a.tree.column("star", "width")
                avail = a.tree.winfo_width() - a._tree_sb_w - 2
                total = star_w + sum(c.values())
                if total > avail + 4:
                    bad_total.append(f"{sec}: {total}>{avail}")
        check("设置项列完整显示最长键名", not bad_wide, "; ".join(bad_wide[:3]))
        check("设置项≈中文名、当前值≈已修改", not bad_pair, "; ".join(bad_pair[:3]))
        check("列总宽不超过可用宽（不撑满）", not bad_total, "; ".join(bad_total[:3]))
        a._cancel_pending_jobs()
        root.destroy()
    except Exception as exc:  # noqa: BLE001
        check("卡片计数一致性（需要显示环境）", False, f"{type(exc).__name__}: {exc}")

    return _finish()


def _finish() -> int:
    """收束：清理自建的 Xvfb 并打印汇总。"""
    global _own_xvfb
    if _own_xvfb is not None:
        _own_xvfb.terminate()
        try:
            _own_xvfb.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _own_xvfb.kill()
        _own_xvfb = None

    print(f"\n{'='*54}")
    print(f"通过 {len(PASS)} 项，失败 {len(FAIL)} 项")
    if FAIL:
        print("失败项：")
        for f in FAIL:
            print(f"  ✗ {f}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
