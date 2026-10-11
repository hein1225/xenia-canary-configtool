#!/usr/bin/env python3
"""海蓝色主题（Ocean Blue）。

设计目标：
  * 以海蓝为主色，营造沉稳、专注的调性，长时间调参不刺眼
  * 明暗对比满足 WCAG AA，掌机小屏与户外光线下属可读
  * 兼容 Tk 的 clam 主题，用 style 覆盖而非自绘控件

配色取自深海到浅滩的过渡：主色 #1B6CA8，强调 #2E9BD6，点缀 #6FD3E8。
"""
from __future__ import annotations

from tkinter import ttk

# ---------------------------------------------------------------- 调色板

PALETTE = {
    # 主体
    "primary": "#1B6CA8",        # 海蓝主色（按钮、选中态）
    "primary_dark": "#12507E",   # 按下态
    "primary_light": "#2E9BD6",  # 悬停态 / 强调
    "accent": "#6FD3E8",         # 浅滩青，用于高亮与图标
    "deep": "#0E3A5C",           # 深海，标题文字与描边

    # 表面
    "surface": "#F5F9FC",        # 面板底色，带一丝蓝调的白
    "surface_alt": "#E8F2F9",    # 交替行 / 卡片底
    "hover": "#D6E9F6",          # 导航悬停底（须够浅：深色文字压上去仍要清晰）
    "surface_card": "#FFFFFF",   # 卡片
    "border": "#BBD6E8",         # 分隔线与边框
    "border_strong": "#8FBEDA",  # 选中卡片边框

    # 文字
    "text": "#0F2433",           # 主文字，近深海的深色
    "text_muted": "#5C7C93",     # 次要说明文字
    "text_inverse": "#FFFFFF",   # 深色底上的文字

    # 状态
    "success": "#1E9E6A",
    "warning": "#C8811A",
    "danger": "#C0392B",
    "modified": "#C8811A",       # 「已修改」标记
}

FONT_FAMILY_PREFS = ("Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei",
                     "DejaVu Sans", "TkDefaultFont")


def pick_font(root) -> str:
    """挑一个可用的无衬线字体，中英文都能正常显示。"""
    try:
        from tkinter import font as tkfont
        available = set(tkfont.families(root))
    except Exception:  # noqa: BLE001
        return "TkDefaultFont"
    for name in FONT_FAMILY_PREFS:
        if name in available:
            return name
    return "TkDefaultFont"


MONO_FONT_PREFS = ("DejaVu Sans Mono", "Liberation Mono", "Noto Sans Mono",
                   "Source Code Pro", "Courier New", "TkFixedFont")


def pick_mono_font(root) -> str:
    """挑一个等宽字体，用于图标列对齐。

    等宽字体保证每个图标占据完全相同的宽度，避免导航栏参差不齐。
    这类字体同时覆盖常用的几何符号（♪ ⚙ ◆ ▣ ▤ ★ ⊕ ⌨ 等）。
    """
    try:
        from tkinter import font as tkfont
        available = set(tkfont.families(root))
    except Exception:  # noqa: BLE001
        return "TkFixedFont"
    for name in MONO_FONT_PREFS:
        if name in available:
            return name
    return "TkFixedFont"


def measure_row_height(root, family: str, size: int) -> int:
    """按字体实际度量算出列表行高。

    直接用 tkfont.Font.metrics("linespace") 拿到该字体的完整行高，
    再加一点内边距。CJK 字体的 linespace 常达 20~26px，写死行高必然
    在某些字体上把长文本行的上下沿挤到一起。
    """
    try:
        from tkinter import font as tkfont
        f = tkfont.Font(root=root, family=family, size=size)
        linespace = int(f.metrics("linespace"))
    except Exception:  # noqa: BLE001
        linespace = 17  # 兜底：常见拉丁字体的行高
    # 行高 >= 字体行高 + 上下各 4px 呼吸空间，并保证一个合理下限
    return max(24, linespace + 8)


def apply_theme(root, compact: bool = False) -> ttk.Style:
    """把海蓝主题应用到 ttk 控件，返回 style 供后续微调。"""
    style = ttk.Style(root)
    for theme in ("clam", "alt", "default"):
        if theme in style.theme_names():
            style.theme_use(theme)
            break

    base_size = 11 if compact else 10
    family = pick_font(root)
    p = PALETTE

    # 让原生 tk 控件（Text/Canvas 等）也用对底色
    try:
        root.configure(background=p["surface"])
    except Exception:  # noqa: BLE001
        pass
    root.option_add("*Font", (family, base_size))
    root.option_add("*Background", p["surface"])
    root.option_add("*Foreground", p["text"])
    root.option_add("*selectBackground", p["primary"])
    root.option_add("*selectForeground", p["text_inverse"])

    # ---- 基础容器
    style.configure(".", background=p["surface"], foreground=p["text"],
                    font=(family, base_size))
    style.configure("TFrame", background=p["surface"])
    style.configure("TLabel", background=p["surface"], foreground=p["text"])
    style.configure("TLabelframe", background=p["surface"], bordercolor=p["border"],
                    relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=p["surface"],
                    foreground=p["deep"], font=(family, base_size + 1, "bold"))
    style.configure("TSeparator", background=p["border"])

    # ---- 按钮
    style.configure("TButton", background=p["primary"], foreground=p["text_inverse"],
                    bordercolor=p["primary_dark"], focuscolor=p["accent"],
                    padding=(12, 8 if compact else 5), relief="flat")
    style.map("TButton",
              background=[("pressed", p["primary_dark"]), ("active", p["primary_light"]),
                          ("disabled", p["surface_alt"])],
              foreground=[("disabled", p["text_muted"])],
              bordercolor=[("active", p["primary_light"])])

    # 侧栏导航：默认浅色，选中/悬停为海蓝
    style.configure("Nav.TButton", background=p["surface_alt"], foreground=p["deep"],
                    anchor="w", padding=(14, 11 if compact else 8),
                    bordercolor=p["border"], relief="flat")
    style.map("Nav.TButton",
              background=[("pressed", p["primary"]), ("active", p["primary_light"])],
              foreground=[("pressed", p["text_inverse"]), ("active", p["text_inverse"])])

    # 次级按钮（还原/说明等）：描边风格
    style.configure("Ghost.TButton", background=p["surface"], foreground=p["primary"],
                    bordercolor=p["primary"], padding=(12, 8 if compact else 5))
    style.map("Ghost.TButton",
              background=[("active", p["surface_alt"]), ("pressed", p["border"])],
              foreground=[("disabled", p["text_muted"])])

    # ---- 输入
    style.configure("TEntry", fieldbackground="#FFFFFF", foreground=p["text"],
                    bordercolor=p["border"], lightcolor=p["border"], darkcolor=p["border"],
                    insertcolor=p["primary"], padding=5)
    style.map("TEntry", bordercolor=[("focus", p["primary"])],
              lightcolor=[("focus", p["primary"])], darkcolor=[("focus", p["primary"])])
    style.configure("TCombobox", fieldbackground="#FFFFFF", background=p["surface_alt"],
                    foreground=p["text"], bordercolor=p["border"], arrowcolor=p["primary"],
                    padding=4)
    style.map("TCombobox",
              fieldbackground=[("readonly", "#FFFFFF")],
              bordercolor=[("focus", p["primary"])])

    style.configure("TCheckbutton", background=p["surface"], foreground=p["text"],
                    focuscolor=p["surface"])
    style.map("TCheckbutton",
              background=[("active", p["surface"])],
              indicatorcolor=[("selected", p["primary"]), ("!selected", "#FFFFFF")])

    # ---- 列表
    # 行高必须按实际字体的度量算，不能写死：CJK 字体（Noto Sans CJK /
    # 文泉驿等）的行高度量明显高于拉丁字体，写死 26px 会让长文本行
    # 上下叠在一起（设置项名那一列最容易暴露）。
    row_h = measure_row_height(root, family, base_size)
    if compact:
        row_h = max(row_h, 30)
    style.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF",
                    foreground=p["text"], bordercolor=p["border"],
                    rowheight=row_h, relief="flat")
    style.map("Treeview",
              background=[("selected", p["primary"])],
              foreground=[("selected", p["text_inverse"])])
    style.configure("Treeview.Heading", background=p["surface_alt"],
                    foreground=p["deep"], relief="flat",
                    font=(family, base_size, "bold"), padding=(6, 7))
    style.map("Treeview.Heading", background=[("active", p["border"])])

    # ---- 滚动条
    style.configure("Vertical.TScrollbar", background=p["surface_alt"],
                    troughcolor=p["surface"], bordercolor=p["surface"],
                    arrowcolor=p["primary"], relief="flat")
    style.map("Vertical.TScrollbar", background=[("active", p["primary_light"])])
    style.configure("Horizontal.TScrollbar", background=p["surface_alt"],
                    troughcolor=p["surface"], bordercolor=p["surface"],
                    arrowcolor=p["primary"], relief="flat")
    style.map("Horizontal.TScrollbar", background=[("active", p["primary_light"])])

    # ---- 语义化文本样式
    style.configure("Section.TLabel", background=p["surface"], foreground=p["deep"],
                    font=(family, base_size + 2, "bold"))
    style.configure("Blurb.TLabel", background=p["surface"], foreground=p["text_muted"],
                    font=(family, base_size - 1 if base_size > 9 else base_size))
    style.configure("CardTitle.TLabel", background=p["surface_card"],
                    foreground=p["deep"], font=(family, base_size + 1, "bold"))
    style.configure("CardBlurb.TLabel", background=p["surface_card"],
                    foreground=p["text_muted"],
                    font=(family, base_size - 1 if base_size > 9 else base_size))
    style.configure("CardCount.TLabel", background=p["surface_card"],
                    foreground=p["primary"])
    style.configure("Hint.TLabel", background=p["surface"], foreground=p["text_muted"])

    # ---- 状态栏
    style.configure("Status.TFrame", background=p["surface_alt"])
    style.configure("Status.TLabel", background=p["surface_alt"], foreground=p["text_muted"])
    style.configure("StatusWarn.TLabel", background=p["surface_alt"], foreground=p["modified"])

    _style_menu(root, family, base_size)
    return style


def _style_menu(root, family: str, base_size: int) -> None:
    """给经典 tk.Menu 上色（ttk 不管菜单）。"""
    p = PALETTE
    try:
        root.option_add("*Menu.background", p["surface_alt"])
        root.option_add("*Menu.foreground", p["text"])
        root.option_add("*Menu.activeBackground", p["primary"])
        root.option_add("*Menu.activeForeground", p["text_inverse"])
        root.option_add("*Menu.selectColor", p["primary"])
        root.option_add("*Menu.relief", "flat")
        root.option_add("*Menu.borderWidth", 0)
        root.option_add("*Menu.Font", (family, base_size))
        root.option_add("*Menubar.background", p["surface_alt"])
        root.option_add("*Menubar.foreground", p["text"])
    except Exception:  # noqa: BLE001
        pass
