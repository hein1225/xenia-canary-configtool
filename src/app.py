#!/usr/bin/env python3
"""Xenia Canary 配置工具 —— 分类导航式图形界面。

界面结构（分类导航展示）：
  ┌──────────┬────────────────────────────┬──────────────┐
  │ 大分类   │ 分组卡片 / 设置列表        │ 设置详情     │
  │ ★ 常用   │ ┌────────┐ ┌────────┐     │ 说明文本     │
  │ ◆ 图形   │ │ 显示   │ │ 图形   │ ... │ 值编辑器     │
  │ ❖ 系统   │ └────────┘ └────────┘     │ 还原按钮     │
  │ ⚒ 开发者 │ ─── 选中分组的设置列表 ─── │              │
  └──────────┴────────────────────────────┴──────────────┘

分组严格来自 xenia-canary.config.toml 的 [Section]，共 22 个，
按玩家使用频率归入 4 个大类；每个分组带图标与一句话说明。

SteamOS / 掌机适配：原生 Wayland 优先、1280x800 自适应、触摸友好尺寸。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------- 显示后端探测
# 必须在导入 tkinter 之前设定环境变量。


def configure_display_backend() -> dict:
    info = {
        "wayland_session": bool(os.environ.get("WAYLAND_DISPLAY")),
        "x11_display": bool(os.environ.get("DISPLAY")),
        "xdg_session": os.environ.get("XDG_SESSION_TYPE", ""),
        "backend": "unknown",
        "notes": [],
    }
    session_type = (os.environ.get("XDG_SESSION_TYPE") or "").lower()
    is_wayland = bool(os.environ.get("WAYLAND_DISPLAY")) or session_type == "wayland"

    if is_wayland:
        info["backend"] = "wayland"
        os.environ.setdefault("GDK_BACKEND", "wayland,x11")
        if not os.environ.get("DISPLAY"):
            info["notes"].append("Wayland 会话：优先原生 Wayland，必要时自动回退 XWayland。")
    elif info["x11_display"]:
        info["backend"] = "x11"
    else:
        info["backend"] = "none"
        info["notes"].append("未检测到 WAYLAND_DISPLAY 或 DISPLAY。")

    if os.environ.get("STEAM_RUNTIME") or Path("/run/steam-runtime").exists():
        info["notes"].append("检测到 Steam Runtime 环境。")
    return info


DISPLAY_INFO = configure_display_backend()

import tkinter as tk  # noqa: E402
from tkinter import filedialog, messagebox, ttk  # noqa: E402

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import navmeta  # noqa: E402
from i18n import LANGUAGE_NAMES, Resources  # noqa: E402
from settings_store import SettingsStore  # noqa: E402
from toml_edit import TomlDoc  # noqa: E402
from theme import PALETTE, apply_theme, pick_mono_font  # noqa: E402
from tooltip import Tooltip, TreeTooltip  # noqa: E402

APP_VERSION = "1.0.0"
COMPACT_WIDTH = 1180


def find_config_file() -> Path | None:
    """按 xenia 的实际查找顺序定位配置文件。"""
    candidates: list[Path] = []
    home = Path.home()

    exe_dir = Path(sys.argv[0]).resolve().parent
    if (exe_dir / "portable.txt").exists():
        candidates.append(exe_dir / "xenia-canary.config.toml")

    xdg_config = os.environ.get("XDG_CONFIG_HOME") or str(home / ".config")
    candidates += [
        Path(xdg_config) / "xenia-canary.config.toml",
        home / ".local/share/xenia-canary/xenia-canary.config.toml",
        home / "xenia-canary.config.toml",
        Path("/usr/share/xenia-canary/xenia-canary.config.toml"),
    ]

    for base in (
        home / ".steam/steam/steamapps/compatdata",
        home / ".local/share/Steam/steamapps/compatdata",
    ):
        if base.is_dir():
            try:
                for p in base.glob("*/pfx/drive_c/users/steamuser/AppData/Roaming/xenia-canary.config.toml"):
                    candidates.append(p)
            except OSError:
                pass

    for c in candidates:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


class ConfigToolApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.res = Resources(APP_DIR / "data")
        self.store = SettingsStore()
        self.lang = self.store.get("language", "zh") or "zh"
        self.auto_backup = bool(self.store.get("auto_backup", True))
        self.show_advanced = bool(self.store.get("show_advanced", False))

        self.doc: TomlDoc | None = None
        self.compare: TomlDoc | None = None
        self.config_path: Path | None = None
        self.defaults: dict = {}
        self.rows: list[dict] = []
        self.selected_key: str | None = None
        self.editor_var = None
        self.editor_widget = None
        self.current_section: str | None = None
        self.active_nav: str = navmeta.NAV_GROUPS[0]["id"]
        self._section_widgets: dict[str, tk.Widget] = {}
        self._building = False
        self._sash_job = None   # 左栏宽度重算的防抖句柄
        self._ready = False   # 控件尚未全部建成前，禁止渲染回调

        self._setup_window()
        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()
        self._ready = True   # 控件齐备，可以安全渲染

        found = self.store.get("last_path") or ""
        path = Path(found) if found and Path(found).is_file() else find_config_file()
        if path:
            self.load_file(path)
        else:
            self.render_all()
            self.set_status(self.t("status_ready"))

    # ------------------------------------------------------------ 工具

    def t(self, key: str, **kw) -> str:
        return self.res.t(self.lang, key, **kw)

    def sec_name(self, section: str) -> str:
        return self.res.section_name(self.lang, section)

    def _setup_window(self) -> None:
        self.root.title(self.t("app_title"))
        self.root.minsize(940, 580)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.compact = sw < COMPACT_WIDTH
        w = min(1280, max(940, int(sw * 0.9)))
        h = min(800, max(580, int(sh * 0.88)))
        self.root.geometry(f"{w}x{h}+{max(0,(sw-w)//2)}+{max(0,(sh-h)//3)}")
        # 启动即最大化：设置项很多，窗口越大一次能看到的条目越多。
        # 必须在 geometry 之后异步调用 —— 窗口尚未映射时调用 zoomed 会被
        # 多数窗口管理器忽略。三种写法按可用性依次降级：
        #   state("zoomed")  X11 惯例，mutter/kwin 支持
        #   -zoomed          Tk 8.6 的 WM 属性写法
        #   -fullscreen      最后手段（无窗口装饰，但至少铺满屏幕）
        self.maximized = False
        self.root.after(120, self._maximize_window)

        base = 11 if self.compact else 10
        try:
            self.root.option_add("*Font", ("TkDefaultFont", base))
        except tk.TclError:
            pass

        self.style = apply_theme(self.root, compact=self.compact)
        from theme import pick_font
        self.ui_font = pick_font(self.root)
        # 图标一律用等宽字体渲染：几何符号在等宽字体下宽度一致，
        # 保证导航栏、分组按钮、卡片、表头的图标严格对齐。
        self.icon_font = pick_mono_font(self.root)
        self.ui_base = 11 if self.compact else 10

    def _maximize_window(self) -> None:
        """尽最大努力把主窗口最大化；失败也不影响使用。

        不同窗口管理器对最大化的支持写法不一，逐个尝试，避免在不支持的
        桌面上抛异常打断启动。
        """
        if getattr(self, "_maximize_off", False):
            return
        try:
            self.root.state("zoomed")
        except tk.TclError:
            for attr in ("-zoomed", "-fullscreen"):
                try:
                    self.root.attributes(attr, True)
                    break
                except tk.TclError:
                    continue
        # 少数 WM 接受调用却静默忽略，延后校验一次实际尺寸，
        # 没变大就退回铺满屏幕的显式尺寸，保证「打开即大窗」。
        self.root.after(180, self._verify_maximized)

    def _verify_maximized(self) -> None:
        """确认窗口确实铺开了；没铺开就改用显式全屏尺寸。"""
        if getattr(self, "_maximize_off", False):
            return
        try:
            if self.root.winfo_width() >= self.root.winfo_screenwidth() - 40:
                self.maximized = True
                return
            self.root.geometry(
                f"{self.root.winfo_screenwidth()}x"
                f"{self.root.winfo_screenheight()}+0+0")
            self.maximized = True
        except tk.TclError:
            pass

    # ------------------------------------------------------------ 图标渲染

    def icon_label(self, icon: str, text: str, pad: int = 2) -> str:
        """把图标与文字组合为对齐的标签。

        图标后的空格数固定，且图标用等宽字体渲染，
        因此所有条目的文字起始位置完全一致。
        """
        return f"{icon}{' ' * pad}{text}"

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda e: self.open_dialog())
        self.root.bind("<Control-s>", lambda e: self.save())
        self.root.bind("<Control-S>", lambda e: self.save_as())
        self.root.bind("<Control-f>", lambda e: self.focus_search())
        self.root.bind("<F5>", lambda e: self.reload())
        self.root.bind("<Control-q>", lambda e: self.on_quit())
        self.root.bind("<Escape>", self._on_escape)
        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)
        self.root.bind("<Configure>", self._on_root_configure)

    def _on_escape(self, _event=None) -> None:
        if self.search_var.get():
            self.search_var.set("")
            self.on_search()
        else:
            self.selected_key = None
            self.render_detail()

    # ------------------------------------------------------------ 菜单

    def _build_menu(self) -> None:
        self.menubar = tk.Menu(self.root)

        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label=self.t("menu_open"), command=self.open_dialog)
        self.file_menu.add_command(label=self.t("menu_reload"), command=self.reload)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=self.t("menu_save"), command=self.save)
        self.file_menu.add_command(label=self.t("menu_save_as"), command=self.save_as)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=self.t("menu_restore_defaults"), command=self.restore_defaults)
        self.file_menu.add_separator()
        self.file_menu.add_command(label=self.t("menu_exit"), command=self.on_quit)
        self.menubar.add_cascade(label=self.t("menu_file"), menu=self.file_menu)

        self.settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.lang_menu = tk.Menu(self.settings_menu, tearoff=0)
        self.lang_var = tk.StringVar(value=self.lang)
        for code in ("zh", "en"):
            self.lang_menu.add_radiobutton(
                label=LANGUAGE_NAMES[code], value=code, variable=self.lang_var,
                command=lambda c=code: self.switch_language(c))
        self.settings_menu.add_cascade(label=self.t("menu_language"), menu=self.lang_menu)
        self.settings_menu.add_separator()

        # 掌机预设：一键套用一组推荐值（写入前需确认）
        self.preset_menu = tk.Menu(self.settings_menu, tearoff=0)
        for p in navmeta.DEVICE_PRESETS:
            pname = p["name"].get(self.lang) or p["name"]["en"]
            self.preset_menu.add_command(
                label=pname, command=lambda pid=p["id"]: self.apply_preset(pid))
        self.settings_menu.add_cascade(label=self.t("menu_presets"), menu=self.preset_menu)
        self.settings_menu.add_separator()
        self.backup_var = tk.BooleanVar(value=self.auto_backup)
        self.settings_menu.add_checkbutton(label=self.t("menu_autobackup"),
                                           variable=self.backup_var, command=self.toggle_backup)
        self.advanced_var = tk.BooleanVar(value=self.show_advanced)
        self.settings_menu.add_checkbutton(label=self.t("menu_show_advanced"),
                                           variable=self.advanced_var, command=self.toggle_advanced)
        self.menubar.add_cascade(label=self.t("menu_settings"), menu=self.settings_menu)

        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.help_menu.add_command(label=self.t("menu_shortcuts"), command=self.show_shortcuts)
        self.help_menu.add_command(label=self.t("menu_about"), command=self.show_about)
        self.menubar.add_cascade(label=self.t("menu_help"), menu=self.help_menu)

        self.root.config(menu=self.menubar)

    # ------------------------------------------------------------ 布局

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill="both", expand=True)

        # ===== 顶部：文件路径与全局操作
        top = ttk.Frame(outer)
        top.pack(fill="x", pady=(0, 8))
        self.path_var = tk.StringVar(value="—")
        self.path_label = ttk.Label(top, textvariable=self.path_var, foreground="#0a7", anchor="w")
        self.path_label.pack(side="left", fill="x", expand=True)

        self.btn_open = ttk.Button(top, text=self.t("menu_open"), command=self.open_dialog)
        self.btn_open.pack(side="right")
        self.btn_save = ttk.Button(top, text=self.t("menu_save"), command=self.save)
        self.btn_save.pack(side="right", padx=5)
        self.btn_refresh = ttk.Button(top, text=self.t("btn_refresh"), command=self.reload)
        self.btn_refresh.pack(side="right", padx=5)

        # ===== 搜索栏
        search = ttk.Frame(outer)
        search.pack(fill="x", pady=(0, 8))
        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True)
        self.search_entry.bind("<Return>", lambda e: self.on_search())
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        self.search_var.trace_add("write", self._toggle_placeholder)

        self.btn_clear = ttk.Button(search, text=self.t("btn_clear"), style="Ghost.TButton",
                                    command=self.clear_search)
        self.btn_clear.pack(side="left", padx=(6, 0))
        self.filter_all_var = tk.BooleanVar(value=True)
        self.chk_filter = ttk.Checkbutton(search, text=self.t("filter_all"),
                                          variable=self.filter_all_var, command=self.render_rows)
        self.chk_filter.pack(side="left", padx=(8, 0))

        # ===== 主体两栏：左导航（固定） + 主区（占满剩余）
        body = ttk.Panedwindow(outer, orient="horizontal")
        body.pack(fill="both", expand=True)

        # --- 左栏：分类导航
        left = ttk.Frame(body)
        self.nav_box = ttk.Frame(left)
        self.nav_box.pack(fill="x")
        ttk.Separator(left, orient="horizontal").pack(fill="x", pady=8)

        self.group_container = ttk.Frame(left)
        self.group_container.pack(fill="both", expand=True)
        body.add(left, weight=0)

        # --- 主区：分组卡片 + 设置列表（+ 底部详情条）
        main = ttk.Frame(body)
        body.add(main, weight=1)

        # 上半：分组卡片区（按内容自适应高度）
        self.cards_host = ttk.Frame(main)
        self.cards_host.pack(fill="x")

        # 底部：详情/编辑条（先 pack 以固定在底部，避免被列表挤走）
        self.detail = ttk.Labelframe(main, text=self.t("detail_title"), padding=8)
        self.detail.pack(side="bottom", fill="x", pady=(8, 0))

        self.detail_meta = ttk.Label(self.detail, text="", foreground=PALETTE["text_muted"],
                                     justify="left", anchor="w")
        self.detail_meta.pack(fill="x", anchor="w")

        row = ttk.Frame(self.detail)
        row.pack(fill="x", pady=(6, 0))
        self.editor_holder = ttk.Frame(row)
        self.editor_holder.pack(side="left", fill="x", expand=True)

        self.btn_revert = ttk.Button(row, text=self.t("detail_revert"), style="Ghost.TButton",
                                     command=self.revert_selected)
        self.btn_revert.pack(side="right", padx=(8, 0))

        # 说明全文按钮：悬停提示看不全时（掌机触摸场景）可弹出完整文本
        self.btn_desc = ttk.Button(row, text=self.t("btn_show_desc"), style="Ghost.TButton",
                                   command=self.show_desc_window)
        self.btn_desc.pack(side="right", padx=(8, 0))

        # 中段：设置列表（填充卡片区与详情条之间的剩余空间）
        self.list_host = ttk.Frame(main)
        self.list_host.pack(fill="both", expand=True, pady=(8, 0))

        # Panedwindow 初始位置：左栏固定宽度
        # 用 after_idle 而非立即设置 —— 此时导航尚未渲染，
        # 直接 sashpos 会被后续内容的请求宽度覆盖。
        self.root.update_idletasks()
        self.root.after_idle(self._apply_sash)

        # ===== 状态栏
        status = ttk.Frame(outer, style="Status.TFrame")
        status.pack(fill="x", pady=(8, 0))
        self.status_var = tk.StringVar(value=self.t("status_ready"))
        ttk.Label(status, textvariable=self.status_var, anchor="w",
                  style="Status.TLabel").pack(side="left", fill="x", expand=True)
        self.modified_var = tk.StringVar(value="")
        ttk.Label(status, textvariable=self.modified_var, anchor="e",
                  style="StatusWarn.TLabel").pack(side="right")

    def _apply_sash(self) -> None:
        """左栏宽度按窗口宽度自适应（比例 + 上下限钳制），窗口缩放时重算。"""
        try:
            body = self.nav_box.master.master  # nav_box -> left -> panedwindow
            win_w = self.root.winfo_width()
            if win_w <= 1:
                win_w = self.root.winfo_reqwidth()
            # 窗口宽度的 20%，钳制在 [220, 340]，保证窄屏不挤压主区、宽屏不留白
            left_w = int(win_w * 0.20)
            left_w = max(220, min(340, left_w))
            # 主区至少保留 560px，避免极窄窗口下列被压没
            if win_w - left_w < 560:
                left_w = max(180, win_w - 560)
            if isinstance(body, ttk.Panedwindow):
                body.sashpos(0, left_w)
        except Exception:
            pass

    def _bind_mousewheel(self, widget) -> None:
        """为需要滚动的控件绑定滚轮（Treeview 自带滚动，无需处理）。"""
        return

    def _main_width(self) -> int:
        """主区实际可用宽度（窗口宽减去左栏实际宽度）。"""
        win_w = self.root.winfo_width()
        if win_w <= 1:
            win_w = self.root.winfo_reqwidth()
        try:
            body = self.nav_box.master.master
            left_w = body.sashpos(0)
        except Exception:
            left_w = 0
        if left_w <= 1:
            left_w = self._left_width_for(win_w)
        return max(320, win_w - left_w)

    @staticmethod
    def _left_width_for(win_w: int) -> int:
        left_w = max(220, min(340, int(win_w * 0.20)))
        if win_w - left_w < 560:
            left_w = max(180, win_w - 560)
        return left_w

    def _on_root_configure(self, event) -> None:
        """窗口尺寸变化时重排左栏宽度与卡片列数。"""
        if event.widget is not self.root or self._building or not self._ready:
            return
        # 左栏按新窗口宽度重算（防抖，避免拖动时抖动）
        if getattr(self, "_sash_job", None) is not None:
            try:
                self.root.after_cancel(self._sash_job)
            except Exception:
                pass
        self._sash_job = self.root.after(60, self._apply_sash)
        cols = self._card_columns(self._main_width())
        if cols != getattr(self, "_card_cols", None):
            self._card_cols = cols
            self.root.after_idle(self.render_rows)

    def _card_columns(self, avail: int) -> int:
        """按可用宽度与当前语言决定卡片列数。

        卡片内容为「图标 + 星标 + 名称 + 计数」。单卡最小宽度不能写死：
        高 DPI（tk scaling 1.5/2.0）下同样的文字会占更宽的像素，写死会让
        卡片里的名称与计数被裁。这里用当前字体实测最长的分组名 + 计数，
        再留出内边距作为单卡需求宽度。
        """
        try:
            avail = int(avail)
        except (TypeError, ValueError):
            avail = 800
        # 取当前语言下最长的分组名作为样本，加上「12」两位计数与星标
        longest = ""
        try:
            for sec in self.res.schema.get("sections", {}):
                name = self.sec_name(sec)
                if len(name) > len(longest):
                    longest = name
        except Exception:  # noqa: BLE001
            longest = ""
        name_w = self._text_width(longest or "Graphics backends", bold=True)
        pad = 28      # 卡片内边距
        icon_w = 20   # 图标列
        star_w = 14   # 前置星标
        count_w = self._text_width("888") + 6
        per_card = max(160, name_w + pad + icon_w + star_w + count_w)
        return max(2, min(6, max(1, avail) // per_card))

    # ------------------------------------------------------------ 语言

    def switch_language(self, lang: str) -> None:
        if lang == self.lang:
            return
        self.lang = lang
        self.store.set("language", lang)
        self.root.title(self.t("app_title"))
        # 英文分组名更长，需重算卡片列数与列表列宽
        self._card_cols = None
        self.refresh_brief_column()
        self._build_menu()
        self.apply_static_texts()
        self.render_all()
        self.render_detail()

    def refresh_brief_column(self) -> None:
        """按当前语言决定「中文名」列是否显示（英文版整列隐藏）。"""
        if self.tree is None:
            return
        visible = self.lang == "zh"
        if visible == getattr(self, "brief_visible", None):
            return
        self.brief_visible = visible
        all_cols = ("star", "key", "brief", "value", "modified")
        self.tree["displaycolumns"] = all_cols if visible else \
            ("star", "key", "value", "modified")
        self.tree.heading("key", text=self.t("col_key"))
        self.tree.heading("brief", text=self.t("col_brief"))
        self.tree.heading("value", text=self.t("col_value"))
        self.tree.heading("modified", text=self.t("col_modified"))

    def apply_static_texts(self) -> None:
        self.btn_open.configure(text=self.t("menu_open"))
        self.btn_save.configure(text=self.t("menu_save"))
        self.btn_refresh.configure(text=self.t("btn_refresh"))
        self.btn_clear.configure(text=self.t("btn_clear"))
        self.btn_revert.configure(text=self.t("detail_revert"))
        self.btn_desc.configure(text=self.t("btn_show_desc"))
        self.chk_filter.configure(text=self.t("filter_all"))
        self.detail.configure(text=self.t("detail_title"))

    # ------------------------------------------------------------ 文件

    def open_dialog(self) -> None:
        initial = str(self.config_path.parent) if self.config_path else str(Path.home())
        path = filedialog.askopenfilename(
            title=self.t("dlg_open_title"), initialdir=initial,
            filetypes=[("TOML", "*.toml"), ("All files", "*.*")])
        if path:
            self.load_file(Path(path))

    def load_file(self, path: Path) -> None:
        try:
            self.doc = TomlDoc.load(path)
            self.compare = TomlDoc.load(path)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.t("dlg_error_title"), self.t("err_load_failed", err=exc))
            return
        self.config_path = path
        self.store.set("last_path", str(path))
        self.path_var.set(str(path))
        self.defaults = {k: self.doc.get(k) for k in self.doc.keys()}
        self.selected_key = None
        self.current_section = None
        self.render_all()
        self.render_detail()
        self.set_status(self.t("status_loaded", path=path))

    def reload(self) -> None:
        if not self.config_path:
            messagebox.showinfo(self.t("dlg_warn_title"), self.t("err_no_file"))
            return
        if self.has_changes() and not messagebox.askyesno(
                self.t("dlg_warn_title"), self.t("ask_discard")):
            return
        self.load_file(self.config_path)

    def save(self) -> None:
        if not self.doc or not self.config_path:
            messagebox.showinfo(self.t("dlg_warn_title"), self.t("err_no_file"))
            return
        if not self.has_changes():
            self.set_status(self.t("status_no_changes"))
            return
        n = len(self.changed_keys())
        note = self.t("dlg_backup_note_on") if self.auto_backup else self.t("dlg_backup_note_off")
        if not messagebox.askyesno(self.t("dlg_confirm_save"),
                                   self.t("dlg_confirm_save_body", path=self.config_path,
                                          n=n, backup_note=note)):
            return
        self._write(self.config_path)

    def save_as(self) -> None:
        if not self.doc:
            messagebox.showinfo(self.t("dlg_warn_title"), self.t("err_no_file"))
            return
        path = filedialog.asksaveasfilename(
            title=self.t("dlg_saveas_title"),
            initialdir=str(self.config_path.parent) if self.config_path else str(Path.home()),
            initialfile=self.config_path.name if self.config_path else "xenia-canary.config.toml",
            defaultextension=".toml", filetypes=[("TOML", "*.toml"), ("All files", "*.*")])
        if path:
            self._write(Path(path))

    def _write(self, path: Path) -> None:
        errs = self.doc.validate()
        if errs:
            messagebox.showerror(self.t("dlg_error_title"), self.t("err_save_failed", err=errs[0]))
            return
        try:
            backup = self.doc.save(path, backup=self.auto_backup)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(self.t("dlg_error_title"), self.t("err_save_failed", err=exc))
            return
        self.config_path = path
        self.doc.path = path
        self.store.set("last_path", str(path))
        self.path_var.set(str(path))
        self.compare = TomlDoc.load(path)
        self.render_rows()
        self.update_modified_count()
        msg = self.t("status_saved", path=path)
        if backup:
            msg += "  |  " + self.t("status_backup", path=backup.name)
        self.set_status(msg)

    # ------------------------------------------------------------ 变更追踪

    def changed_keys(self) -> list[str]:
        if not self.doc or not self.compare:
            return []
        return [k for k in self.doc.keys() if self.doc.get(k) != self.compare.get(k)]

    def has_changes(self) -> bool:
        return bool(self.changed_keys())

    def is_modified(self, key: str) -> bool:
        if not self.doc or not self.compare or key not in self.doc.index:
            return False
        if key not in self.compare.index:
            return True
        return self.doc.get(key) != self.compare.get(key)

    def update_modified_count(self) -> None:
        n = len(self.changed_keys())
        # 状态栏可能在首次渲染时尚未创建（load_file 早于 _build_ui 完成）
        var = getattr(self, "modified_var", None)
        if var is not None:
            var.set(self.t("status_modified_count", n=n) if n else "")

    # ------------------------------------------------------------ 分类导航渲染

    def visible_nav_groups(self) -> list[dict]:
        """开发者大类是否展示由开关决定。"""
        return [g for g in navmeta.NAV_GROUPS if self.show_advanced or g["id"] != "developer"]

    def _cfg_values(self) -> dict:
        """当前配置的值表，供依从规则判断。

        每次重建 267 项的字典在切换分组时会被反复调用（卡片计数、
        分组可见性都依赖它），因此按编辑版本号缓存；任何写入都走
        _bump_doc_version() 使缓存失效。
        """
        if self.doc is None:
            return {}
        ver = getattr(self, "_doc_version", 0)
        cache = getattr(self, "_cfg_vals_cache", None)
        if cache is not None and cache[0] == ver:
            return cache[1]
        vals = {k: self.doc.get(k) for k in self.doc.keys()}
        self._cfg_vals_cache = (ver, vals)
        return vals

    def _bump_doc_version(self) -> None:
        """配置值发生变化后调用，令 _cfg_values / 计数缓存失效。"""
        self._doc_version = getattr(self, "_doc_version", 0) + 1
        self._cfg_vals_cache = None
        self._vis_count_cache = None

    def visible_sections(self, nav_id: str) -> list[str]:
        """大类下应当显示的分组：按后端依从关系过滤。"""
        vals = self._cfg_values()
        out = []
        for g in navmeta.NAV_GROUPS:
            if g["id"] != nav_id:
                continue
            for s in g["sections"]:
                if s not in self.res.schema.get("sections", {}):
                    continue
                if navmeta.group_visible(vals, s):
                    out.append(s)
        return out

    def hidden_sections(self, nav_id: str) -> list[str]:
        """当前被依从规则隐藏的分组（供界面给出说明入口）。"""
        vals = self._cfg_values()
        out = []
        for g in navmeta.NAV_GROUPS:
            if g["id"] != nav_id:
                continue
            for s in g["sections"]:
                if s in self.res.schema.get("sections", {}) and not navmeta.group_visible(vals, s):
                    out.append(s)
        return out

    def render_all(self) -> None:
        self.render_nav()
        self.render_nav_sections()
        self.render_rows()

    # ------------------------------------------------------------ 对齐的导航条目

    def _nav_row(self, parent, icon: str, text: str, suffix: str, active: bool,
                 on_click, tooltip: str | None = None):
        """构建一条左右对齐的导航项。

        图标用等宽字体单独渲染并固定宽度，文字用界面字体，
        因此不同宽度字形的图标不会让文字起点参差不齐。
        """
        bg = PALETTE["primary_dark"] if active else PALETTE["surface"]
        fg = "#FFFFFF" if active else PALETTE["deep"]
        border = PALETTE["primary_dark"] if active else PALETTE["surface"]

        row = tk.Frame(parent, background=bg, highlightthickness=1,
                       highlightbackground=border, highlightcolor=border,
                       cursor="hand2")
        row.pack(fill="x", pady=1)

        inner = tk.Frame(row, background=bg)
        inner.pack(fill="x", padx=8, pady=4)

        # 图标：等宽字体 + 固定字符位，保证所有条目的图标列等宽
        ic = tk.Label(inner, text=icon, background=bg,
                      foreground="#FFFFFF" if active else PALETTE["primary"],
                      font=(self.icon_font, self.ui_base + 1), width=2, anchor="center")
        ic.pack(side="left")

        # 计数/后缀右对齐，文字过长时先压缩它。
        # 计数为 0 时用警告色 + 加粗，提醒「这组点进去是空的」——
        # 否则它与其它数字长得一样，用户只会以为自己点错了。
        sfx = None
        if suffix:
            zero = suffix == "0"
            sfx = tk.Label(inner, text=suffix, background=bg,
                           foreground=(PALETTE["modified"] if zero else
                                       ("#D8ECFA" if active else PALETTE["text_muted"])),
                           font=(self.ui_font, max(8, self.ui_base - 1),
                                 "bold" if zero else "normal"), anchor="e")
            sfx.pack(side="right", padx=(6, 0))

        tx = tk.Label(inner, text=text, background=bg, foreground=fg,
                      font=(self.ui_font, self.ui_base, "bold" if active else "normal"),
                      anchor="w")
        tx.pack(side="left", fill="x", expand=True, padx=(4, 0))

        widgets = [row, inner, ic, tx] + ([sfx] if sfx else [])

        # 悬停配色：底色必须足够浅，且文字/图标颜色要跟着变深。
        # 曾用 primary_light(#2E9BD6) 做悬停底，但条目文字是 deep(#0E3A5C)，
        # 对比度只有 3.81:1（低于无障碍 4.5:1），悬停时字几乎看不清。
        # 现在改用更浅的 hover 底色，文字统一转为最深的 text 色。
        if active:
            hover_bg, hover_fg, hover_ic, hover_sfx = (
                PALETTE["primary_dark"], "#FFFFFF", "#FFFFFF", "#D8ECFA")
        else:
            hover_bg = PALETTE.get("hover", PALETTE["surface_alt"])
            hover_fg = PALETTE["text"]
            hover_ic = PALETTE["primary_dark"]
            hover_sfx = PALETTE["primary_dark"]

        def _paint(background: str, fg: str, ic_fg: str, sfx_fg: str) -> None:
            row.configure(background=background, highlightbackground=background,
                          highlightcolor=background)
            inner.configure(background=background)
            ic.configure(background=background, foreground=ic_fg)
            tx.configure(background=background, foreground=fg)
            if sfx is not None:
                sfx.configure(background=background, foreground=sfx_fg)

        # 零值计数的常态色需单独记录，否则鼠标移开后会退回灰色、失去警示作用
        sfx_idle = (PALETTE["modified"] if suffix == "0" else
                    ("#D8ECFA" if active else PALETTE["text_muted"]))
        for w in widgets:
            w.bind("<Button-1>", lambda e: on_click())
            w.bind("<Enter>", lambda e: _paint(hover_bg, hover_fg, hover_ic,
                                               PALETTE["modified"] if suffix == "0" else hover_sfx))
            w.bind("<Leave>", lambda e: _paint(bg, fg, "#FFFFFF" if active else PALETTE["primary"],
                                               sfx_idle))
        row._suffix_widget = sfx          # 供 _restyle_group_cards 直接改计数色
        if tooltip:
            self._register_tip(Tooltip(row, tooltip, wraplength=300, delay=600))
        return row

    def render_nav(self) -> None:
        """渲染左侧大分类导航。"""
        for w in self.nav_box.winfo_children():
            w.destroy()
        self.nav_rows: dict[str, tk.Frame] = {}

        if not getattr(self, "active_nav", None):
            self.active_nav = self.visible_nav_groups()[0]["id"]

        for g in self.visible_nav_groups():
            name = g["name"].get(self.lang) or g["name"]["en"]
            desc = g["desc"].get(self.lang) or g["desc"]["en"]
            n_sec = len(g["sections"])
            n_key = sum(len(self.res.schema.get("sections", {}).get(s, []))
                        for s in g["sections"])
            row = self._nav_row(
                self.nav_box, g["icon"], name,
                self.t("nav_item_count", n=n_key),
                g["id"] == self.active_nav,
                lambda gid=g["id"]: self.select_nav(gid),
                tooltip=f"{name}\n\n{desc}\n\n{n_sec} {self.t('unit_sections')} · "
                        f"{n_key} {self.t('unit_items')}",
            )
            self.nav_rows[g["id"]] = row

        self.render_group_tree()

    def render_group_tree(self) -> None:
        """渲染当前大分类下的分组入口。

        卡片节点本身缓存复用：切换大分类时若分组列表没变（比如在
        「常用设置」和「图形后端」之间来回点，多数分组重叠），只重刷
        选中态配色，不销毁重建。重建 22 张卡片要 400+ 次 bind 加 22 个
        Tooltip，是切换卡顿的主因。
        """
        secs = list(self.visible_sections(self.active_nav))
        cache_key = (tuple(secs), self.lang)
        counts = tuple(self._section_visible_count(s)[0] for s in secs)
        if getattr(self, "_group_cache_key", None) == cache_key and \
                getattr(self, "_group_cache_counts", None) == counts:
            self._restyle_group_cards()
            return
        self._group_cache_key = cache_key
        self._group_cache_counts = counts
        for w in self.group_container.winfo_children():
            w.destroy()
        ttk.Label(self.group_container,
                  text=self.t("nav_sections", n=len(secs)),
                  style="Blurb.TLabel").pack(anchor="w", pady=(0, 4))
        self.group_rows: dict[str, tk.Frame] = {}
        for sec, count in zip(secs, counts):
            blurb = navmeta.nav_blurb(self.lang, sec)
            self.group_rows[sec] = self._nav_row(
                self.group_container, navmeta.nav_icon(sec), self.sec_name(sec),
                str(count), sec == self.current_section,
                lambda s=sec: self.select_section(s),
                tooltip=f"{self.sec_name(sec)}\n\n{blurb}" if blurb else None,
            )

    def _restyle_group_cards(self) -> None:
        """分组列表未变时，只把卡片的选中态配色刷一遍（比重建快一个数量级）。"""
        for sec, row in self.group_rows.items():
            active = sec == self.current_section
            bg = PALETTE["surface_alt"] if active else PALETTE["surface_card"]
            fg = PALETTE["deep"] if active else PALETTE["primary_dark"]
            ic_fg = PALETTE["primary"] if active else PALETTE["primary_dark"]
            try:
                row.configure(background=bg, highlightthickness=1,
                              highlightbackground=PALETTE["primary"] if active
                              else PALETTE["border"])
                self._repaint_nav_row(row, bg, fg, ic_fg, fg, active)
            except tk.TclError:
                pass

    def select_nav(self, nav_id: str) -> None:
        self.active_nav = nav_id
        self.current_section = None
        # 这里必须把前景色一并重置。只刷 background 会让「刚被取消选中的」
        # 那一项停留在浅底 + 白字的状态，文字直接看不见（曾真实发生：
        # 切到「图形后端」后「常用设置」整行消失了）。
        for gid, row in self.nav_rows.items():
            active = gid == nav_id
            bg = PALETTE["primary_dark"] if active else PALETTE["surface"]
            fg = "#FFFFFF" if active else PALETTE["deep"]
            ic_fg = "#FFFFFF" if active else PALETTE["primary"]
            sfx_fg = "#D8ECFA" if active else PALETTE["text_muted"]
            row.configure(background=bg, highlightbackground=bg, highlightcolor=bg)
            self._repaint_nav_row(row, bg, fg, ic_fg, sfx_fg)
        self.render_group_tree()

    def _repaint_nav_row(self, widget, bg: str, fg: str, ic_fg: str,
                         sfx_fg: str, bold: bool | None = None) -> None:
        """把一条导航项整棵子树重刷成指定配色。

        计数标签（纯数字或「N 项」）用 sfx_fg，图标用 ic_fg，
        其余文字用 fg。零值计数保持橙色警示，不随选中态变化。
        bold 为 None 时不改字重；卡片重刷选中态时传 True/False。
        """
        for child in widget.winfo_children():
            try:
                txt = str(child.cget("text"))
            except tk.TclError:
                txt = None
            if txt is not None and isinstance(child, tk.Label):
                if txt == "0":
                    child.configure(background=bg, foreground=PALETTE["modified"])
                elif txt.endswith("项") or txt.isdigit():
                    child.configure(background=bg, foreground=sfx_fg)
                elif len(txt) == 1:      # 图标
                    child.configure(background=bg, foreground=ic_fg)
                else:
                    child.configure(background=bg, foreground=fg)
                    if bold is not None:
                        fam = child.cget("font")
                        child.configure(font=(self.ui_font, self.ui_base,
                                              "bold" if bold else "normal"))
            else:
                try:
                    child.configure(background=bg)
                except tk.TclError:
                    pass
            self._repaint_nav_row(child, bg, fg, ic_fg, sfx_fg, bold)

    def select_section(self, section: str, focus_key: str | None = None) -> None:
        self.current_section = None if self.current_section == section and not focus_key else section
        # 卡片列表此时通常已存在（缓存命中），只需刷新选中态配色，
        # 不必重建整棵分组树。
        if getattr(self, "group_rows", None):
            self._restyle_group_cards()
        else:
            self.render_group_tree()
        # 切分组只影响下方列表：卡片区内容一字未变，重建它要花约 700ms
        # （真机实测占整次切换 85%）。这里明确跳过，只重建列表。
        self.render_rows(cards=False)
        if focus_key:
            self.root.after_idle(lambda k=focus_key: self._focus_key(k))

    def _focus_key(self, key: str) -> None:
        """在列表中选中并滚动到指定设置项。"""
        if self.tree is None:
            return
        try:
            for iid in self.tree.get_children():
                if self.tree.set(iid, "key") == key:
                    self.tree.selection_set(iid)
                    self.tree.focus(iid)
                    self.tree.see(iid)
                    self.on_row_select(None)
                    return
        except tk.TclError:
            pass

    def render_nav_sections(self) -> None:
        pass  # 分组卡片在中栏渲染

    # ------------------------------------------------------------ 中栏：卡片 + 列表

    def render_rows(self, cards: bool = True) -> None:
        """重建主区：上方分组卡片总览，下方当前范围的设置列表。

        cards=False 时**不碰卡片区**。切换分组只改变下方列表，卡片区内容
        完全没变，却要 destroy + 重建 8 个卡片容器（真机实测约 700ms，占
        整次切换耗时的 85%）。切分组时传 False 即可跳过。
        """
        if self._building or not self._ready:
            return
        self._building = True
        try:
            if cards:
                self._render_cards_area()

            # ---------- 下：设置列表 ----------
            if self.doc is not None and self._try_reuse_settings_list():
                pass  # 已复用现有控件，只更新了内容
            else:
                for w in self.list_host.winfo_children():
                    w.destroy()
                self._settings_ui = None
                if self.doc is None:
                    self._render_empty_state(self.list_host)
                else:
                    self._render_settings_list(self.list_host)
        finally:
            self._building = False
        self.update_modified_count()

    def _render_cards_area(self) -> None:
        """重建上方卡片区（标题 + 分组卡片 + 隐藏提示）。"""
        for w in self.cards_host.winfo_children():
            w.destroy()
        # 控件已销毁，角标登记表必须同步作废，否则就地刷新会摸到死控件
        self.card_badges = {}

        nav = next((g for g in navmeta.NAV_GROUPS if g["id"] == self.active_nav), None)
        if nav:
            head = ttk.Frame(self.cards_host)
            head.pack(fill="x", pady=(0, 2))
            ttl = tk.Frame(head, background=PALETTE["surface_alt"])
            ttl.pack(anchor="w")
            tk.Label(ttl, text=nav["icon"], background=PALETTE["surface_alt"],
                     foreground=PALETTE["primary"],
                     font=(self.icon_font, self.ui_base + 3), width=2,
                     anchor="center").pack(side="left")
            tk.Label(ttl, text=nav["name"].get(self.lang) or nav["name"]["en"],
                     background=PALETTE["surface_alt"], foreground=PALETTE["deep"],
                     font=(self.ui_font, self.ui_base + 2, "bold"),
                     anchor="w").pack(side="left", padx=(4, 0))
            ttk.Label(head, text=nav["desc"].get(self.lang) or nav["desc"]["en"],
                      style="Blurb.TLabel", wraplength=860,
                      justify="left").pack(anchor="w", pady=(2, 6))

            cards = ttk.Frame(self.cards_host)
            cards.pack(fill="x")
            avail = self.cards_host.winfo_width() or self.root.winfo_width() - 280
            cols = self._card_columns(avail)
            for i, sec in enumerate(self.visible_sections(self.active_nav)):
                self._make_card(cards, sec, i, cols)

            # 被依从规则隐藏的分组：说明原因并提供一键切换
            # 注意：卡片区用 grid 排布，提示条必须放到同级但独立的容器，
            # 否则会被网格列宽挤压、文字溢出到可视区外。
            hidden = self.hidden_sections(self.active_nav)
            if hidden:
                notice_host = ttk.Frame(self.cards_host)
                notice_host.pack(fill="x", pady=(8, 0))
                self._render_hidden_notice(notice_host, hidden)


    def _render_empty_state(self, parent) -> None:
        box = ttk.Frame(parent, padding=(4, 20))
        box.pack(fill="x")
        ttk.Label(box, text=self.t("empty_title"), style="Section.TLabel").pack(anchor="w")
        ttk.Label(box, text=self.t("empty_body"), style="Blurb.TLabel",
                  wraplength=620, justify="left").pack(anchor="w", pady=(6, 12))
        ttk.Button(box, text=self.t("menu_open"),
                   command=self.open_dialog).pack(anchor="w")
        ttk.Label(box, text=self.t("empty_hint_paths"), style="Blurb.TLabel",
                  wraplength=620, justify="left").pack(anchor="w", pady=(12, 0))

    def _keys_of_section(self, section: str) -> list[str]:
        """本分组能出现的全部键（schema 归属 + 依从项额外归属），带缓存。

        遍历 267 条 entries 去找 also_in_section 匹配项，代价不低，
        而分组列表每次切换都会对 22 个分组各调一次，必须缓存。
        """
        cache = getattr(self, "_sec_keys_cache", None)
        if cache is None:
            cache = self._sec_keys_cache = {}
        if section in cache:
            return cache[section]
        keys = list(self.res.schema.get("sections", {}).get(section, []))
        for e in self.res.schema.get("entries", []):
            k = e.get("key")
            if k and navmeta.also_in_section(k) == section and k not in keys:
                keys.append(k)
        cache[section] = keys
        return keys

    def _section_visible_count(self, section: str) -> tuple[int, str]:
        """某分组在当前视图下**实际**能列出的项数，以及数量为 0 的原因。

        不能直接用 schema 里的键数：高级项在非「开发者选项」大类下会被隐藏，
        像 Kernel(16)、Logging(12) 这类整组都是高级项的分组，卡片上写着 16/12，
        点进去却一条都没有。卡片必须显示真实数量，否则就是误导。

        返回 (可见项数, 原因)：reason 为 "" 或 "advanced"。

        计数口径必须与 _fill_tree 的过滤完全一致，否则卡片数字和实际列出的
        条数会对不上。除高级项外还要算上两类：
          · 依从项 —— render_target_path_* 会额外出现在对应后端分组下（also_in）；
          · 后端可见性 —— 不适用当前 gpu 取值的项被 key_visible 隐藏。
        """
        if self.doc is None:
            return len(self.res.schema.get("sections", {}).get(section, [])), ""

        vals = self._cfg_values()
        keys = self._keys_of_section(section)

        n = 0
        n_adv = 0
        for k in keys:
            if k not in self.doc.index:
                continue
            if not navmeta.key_visible(vals, k):
                continue
            if not self.show_advanced and self.active_nav != "developer" and \
                    self._is_advanced(k):
                n_adv += 1
                continue
            n += 1
        if n == 0 and n_adv > 0:
            return 0, "advanced"
        return n, ""

    def _is_advanced(self, key: str) -> bool:
        """该设置是否为高级项（惰性建索引，避免每帧线性扫描 entries）。"""
        idx = getattr(self, "_advanced_index", None)
        if idx is None:
            idx = {e["key"]: bool(e.get("advanced"))
                   for e in self.res.schema.get("entries", [])}
            self._advanced_index = idx
        return idx.get(key, False)

    def _make_card(self, parent, section: str, idx: int, cols: int) -> None:
        keys = self.res.schema.get("sections", {}).get(section, [])
        # 卡片上的数字用「实际可见项数」，不是 schema 里的键数 —— 否则
        # 高级项分组会显示 16/12 却点进去空空如也。
        n_vis, left_which = self._section_visible_count(section)
        modified = sum(1 for k in keys if self.is_modified(k))
        active = self.current_section == section

        # 选中态必须「更重」而不是「更浅」：未选中用中等海蓝（primary_dark，
        # 白底 8.5:1），选中用最深色（deep，11.8:1）+ 浅蓝底 + 加粗边框 + 2px 描边。
        # 反过来的话（未选中 deep、选中 primary）会让人误以为没选中的那张才是高亮的。
        card_bg = PALETTE["surface_alt"] if active else PALETTE["surface_card"]
        name_fg = PALETTE["deep"] if active else PALETTE["primary_dark"]
        card = tk.Frame(parent, relief="solid", borderwidth=2 if active else 1,
                        background=card_bg,
                        highlightthickness=1,
                        highlightbackground=PALETTE["primary"] if active else PALETTE["border"],
                        highlightcolor=PALETTE["primary"])
        card.grid(row=idx // cols, column=idx % cols, padx=4, pady=4, sticky="nsew")
        parent.columnconfigure(idx % cols, weight=1)

        inner = tk.Frame(card, background=card_bg)
        inner.pack(fill="both", expand=True, padx=10, pady=9)

        # 紧凑单行布局：图标列固定宽度（等宽字体），名称紧随其后
        top = tk.Frame(inner, background=card_bg)
        top.pack(fill="x", anchor="w")

        ic = tk.Label(top, text=navmeta.nav_icon(section), anchor="center",
                      background=card_bg,
                      foreground=PALETTE["primary"] if active else PALETTE["primary_dark"],
                      font=(self.icon_font, self.ui_base + 1), width=2)
        ic.pack(side="left")

        # 含常用推荐项的分组用星号标记，与左栏导航的图标列宽严格一致
        n_feat = sum(1 for k in keys if k in navmeta.FEATURED_KEYS)
        star = tk.Label(top, text="✳" if n_feat else " ", anchor="center",
                        background=card_bg,
                        foreground=PALETTE["modified"],
                        font=(self.icon_font, self.ui_base), width=2)
        star.pack(side="left")

        lbl = tk.Label(top, text=self.sec_name(section), anchor="w", justify="left",
                       background=card_bg,
                       foreground=name_fg,
                       font=(self.ui_font, self.ui_base, "bold" if active else "normal"))
        lbl.pack(side="left", padx=(4, 0))

        # 显示实际可见项数；整组被隐藏时用「0」提示，而不是骗人的 schema 总数
        cnt = str(n_vis)
        empty = n_vis == 0 and left_which == "advanced"
        cd = tk.Label(top, text=cnt, anchor="e",
                      background=card_bg,
                      foreground=PALETTE["warning"] if empty else
                      (PALETTE["modified"] if modified else
                       (PALETTE["primary_dark"] if active else PALETTE["text_muted"])),
                      font=(self.ui_font, max(8, self.ui_base - 1), "bold" if active else "normal"))
        cd.pack(side="right")

        widgets = [card, inner, top, ic, star, lbl, cd]
        # 登记角标控件：改设置项后只需就地改这一个 Label 的文字与颜色，
        # 不必重建整片卡片区（真机实测重建约 700ms）。
        self.card_badges[section] = (cd, card_bg, empty)

        # 整张卡片可点击；悬停高亮并显示分组简介
        blurb = navmeta.nav_blurb(self.lang, section)
        tip_text = f"{self.sec_name(section)}  ({section})"
        if blurb:
            tip_text += f"\n\n{blurb}"
        be = navmeta.BACKEND_SECTIONS.get(section)
        if be:
            tip_text += "\n\n" + self.t("backend_tip", value=be)
        # 项数用「实际可见数」；若该组项全部被隐藏，直接在提示里说明原因和出路
        if left_which == "advanced":
            tip_text += f"\n\n{self.t('card_all_advanced', n=len(keys))}"
        else:
            tip_text += f"\n\n{n_vis} {self.t('unit_items')}"
        if n_feat:
            tip_text += f"  ·  {self.t('card_featured_n', n=n_feat)}"
        for w in widgets:
            w.bind("<Button-1>", lambda e, s=section: self.select_section(s))
            w.bind("<Enter>", lambda e, c=card: c.configure(
                highlightbackground=PALETTE["primary"], highlightcolor=PALETTE["primary"]))
            w.bind("<Leave>", lambda e, c=card, a=active: c.configure(
                highlightbackground=PALETTE["primary"] if a else PALETTE["border"],
                highlightcolor=PALETTE["primary"]))
            w.configure(cursor="hand2")
            self._register_tip(Tooltip(w, tip_text, wraplength=320, delay=500))

    def _render_hidden_notice(self, parent, hidden: list[str]) -> None:
        """提示哪些分组因当前后端设置而未显示，并给出切换入口。"""
        vals = self._cfg_values()
        box = tk.Frame(parent, background=PALETTE["surface_card"],
                       highlightbackground=PALETTE["border_strong"],
                       highlightthickness=1)
        box.pack(fill="x", expand=True)
        inner = tk.Frame(box, background=PALETTE["surface_card"])
        inner.pack(fill="x", padx=10, pady=8)

        tk.Label(inner, text="⊘", font=(self.icon_font, self.ui_base + 1),
                 width=2, anchor="center", background=PALETTE["surface_card"],
                 foreground=PALETTE["text_muted"]).pack(side="left", padx=(0, 6))

        txt = tk.Frame(inner, background=PALETTE["surface_card"])
        txt.pack(side="left", fill="x", expand=True)
        names = "、".join(self.sec_name(s) for s in hidden) if self.lang == "zh" \
            else ", ".join(self.sec_name(s) for s in hidden)
        tk.Label(txt, text=self.t("hidden_head", names=names),
                 background=PALETTE["surface_card"], foreground=PALETTE["deep"],
                 font=(self.ui_font, self.ui_base, "bold"),
                 anchor="w", justify="left").pack(anchor="w", fill="x")
        reasons = []
        for s in hidden:
            r = navmeta.hidden_reason(vals, s)
            reasons.append(f"{self.sec_name(s)} → {r}" if r else self.sec_name(s))
        tk.Label(txt, text=self.t("hidden_body", detail="；".join(reasons)),
                 background=PALETTE["surface_card"], foreground=PALETTE["text_muted"],
                 font=(self.ui_font, max(8, self.ui_base - 1)),
                 anchor="w", justify="left", wraplength=780).pack(anchor="w", fill="x", pady=(2, 0))

    def _render_settings_list(self, parent) -> None:
        sec = self.current_section
        title = self.sec_name(sec) if sec else self.t("list_all_sections")
        head = ttk.Frame(parent)
        head.pack(fill="x", pady=(4, 4))
        title_lbl = ttk.Label(head, text=title, style="Section.TLabel")
        title_lbl.pack(side="left")
        back_btn = None
        if sec:
            back_btn = ttk.Button(head, text=self.t("btn_back_all"),
                                  command=lambda: self.select_section(sec))
            back_btn.pack(side="right")

        # 后端专属分组：提示它与 gpu 项的从属关系，并可一键跳过去改
        be = navmeta.BACKEND_SECTIONS.get(sec) if sec else None
        if be:
            cur = str(self.doc.get(navmeta.BACKEND_CHOICE_KEY)).strip().strip('"').lower()
            active = cur == be
            vals = self._cfg_values()
            n_hidden = sum(1 for e in self.res.schema.get("entries", [])
                           if e.get("section") == sec and not navmeta.key_visible(vals, e["key"]))

            bar = ttk.Frame(parent)
            bar.pack(fill="x", pady=(0, 6))
            inner = tk.Frame(bar, background=PALETTE["surface_alt"],
                             highlightbackground=PALETTE["border_strong"],
                             highlightthickness=1)
            inner.pack(fill="x")
            ic = tk.Label(inner, text="◈", font=(self.icon_font, self.ui_base + 1),
                          width=2, anchor="center",
                          background=PALETTE["surface_alt"],
                          foreground=PALETTE["primary"])
            ic.pack(side="left", padx=(8, 6))

            txt = tk.Frame(inner, background=PALETTE["surface_alt"])
            txt.pack(side="left", fill="x", expand=True, pady=6)
            head = self.t("backend_bar_active" if active else "backend_bar",
                          value=navmeta.BACKEND_LABELS.get(be, {}).get(self.lang, be))
            tk.Label(txt, text=head, justify="left", anchor="w",
                     background=PALETTE["surface_alt"],
                     foreground=PALETTE["primary"] if active else PALETTE["deep"],
                     font=(self.ui_font, self.ui_base, "bold")).pack(anchor="w", fill="x")
            sub = self.t("backend_sub")
            if n_hidden:
                sub += "  " + self.t("dep_hidden_n", n=n_hidden)
            tk.Label(txt, text=sub, justify="left", anchor="w", wraplength=700,
                     background=PALETTE["surface_alt"], foreground=PALETTE["text_muted"],
                     font=(self.ui_font, max(8, self.ui_base - 1))).pack(anchor="w", fill="x")

            if not active:
                ttk.Button(inner, text=self.t("backend_go"),
                           command=lambda: self.select_section(
                               "GPU", focus_key=navmeta.BACKEND_CHOICE_KEY)
                           ).pack(side="right", padx=8, pady=6)

        # 空列表提示条容器：排在 wrap **之前** 并 pack(fill="x")。
        # 若放在 wrap（expand=True）之后，会被列表撑到可视区外，用户根本看不到。
        # 有内容时该容器恒为空（不占高度），因此正常视图不受影响。
        self._list_hint_host = ttk.Frame(parent)
        self._list_hint_host.pack(fill="x")

        self._tree_wrap = ttk.Frame(parent)
        self._tree_wrap.pack(fill="both", expand=True)
        wrap = self._tree_wrap

        cols = ("star", "key", "brief", "value", "modified")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("star", text="✳")
        self.tree.heading("key", text=self.t("col_key"))
        self.tree.heading("brief", text=self.t("col_brief"))
        self.tree.heading("value", text=self.t("col_value"))
        self.tree.heading("modified", text=self.t("col_modified"))
        # 「说明」列只在中文版出现：英文版没有中文名，整列（含表头）隐藏
        self.brief_visible = self.lang == "zh"
        if not self.brief_visible:
            self.tree["displaycolumns"] = ("star", "key", "value", "modified")
        # 行高必须按界面字体的真实行距设置。
        # ttk.Treeview 默认行高是写死的像素值，在 1.0 缩放的机器上
        # CJK 字体行距比默认值大，行内容会被上下裁掉（真机 1280x852 实测）。
        # 用字体度量算出真实行距再加内边距，缩放/字体变化时都够用。
        try:
            import tkinter.font as tkfont
            _f = tkfont.Font(root=self.root, family=self.ui_font,
                             size=self.ui_base, weight="normal")
            _row_h = max(24, _f.metrics("linespace") + 10)
        except Exception:
            _row_h = 28
        _style = ttk.Style(self.root)
        _style.configure("Treeview", rowheight=_row_h)
        _style.configure("Treeview.Heading",
                         font=(self.ui_font, self.ui_base, "bold"))
        self._row_height = _row_h

        # 列宽在 _apply_tree_columns() 中按容器真实宽度分配（含窗口缩放时重算）
        self.tree.tag_configure("featured", foreground=PALETTE["modified"])
        self._col_job = None
        self._last_avail = 0
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self._tree_sb_w = 18  # 预留纵向滚动条宽度，避免列被挤出可视区
        self.tree.bind("<Configure>", self._on_tree_configure)
        self.tree.bind("<<TreeviewSelect>>", self.on_row_select)
        self.tree.bind("<Double-1>", self._on_tree_double)
        # 触摸屏：长按（无 hover）也能唤出说明
        self.tree.bind("<ButtonPress-1>", self._on_tree_press, add="+")
        self.tree.bind("<ButtonRelease-1>", self._on_tree_release, add="+")

        # 悬停显示该设置项的完整说明（替代常驻说明面板，节省横向空间）
        self._tree_tip = TreeTooltip(self.tree, self._tooltip_text,
                                     wraplength=560 if not self.compact else 460)
        self._register_tip(self._tree_tip)
        # 立即按当前容器宽度分配一次（此时 list_host 已可量宽）
        self.root.after_idle(self._apply_tree_columns)
        # 列表填充后若一条都没有，说明原因 —— 否则用户点进 Kernel/日志 这类
        # 整组都是高级项的分组，只会看到一片空白，不知道该改什么
        self.root.after_idle(self._render_list_hint_if_empty)
        # 列宽按当前分组的实际内容重算（键名长度、值长度、中文名长度都随分组变化）。
        # 不重算的话，切换分组后仍沿用上一组的宽度，出现截断或大片空白。
        # refill=False：列表刚由本方法填过，不必再填一遍。
        self.root.after_idle(lambda: self._apply_tree_columns(refill=False))

        # 登记本次构建的控件，供 _try_reuse_settings_list 复用：
        # 切分组时真正变的只有标题文字和表格行数据，整棵控件树（Treeview、
        # 表头、滚动条、事件绑定、tooltip）都无需重建。真机实测重建一次
        # 约 300ms，是所有切换延迟的主要来源。
        self._settings_ui = {
            "parent": parent,
            "title": title_lbl,
            "back": back_btn,
            "lang": self.lang,
            "backend_bar": be is not None,
        }

    def _try_reuse_settings_list(self) -> bool:
        """复用已有的列表控件，只更新内容。返回 True 表示复用成功。

        复用条件：控件树还在，且语言没变 —— 语言变了表头文字与「中文名」
        列的显隐都要跟着变，走重建更稳妥。
        """
        ui = getattr(self, "_settings_ui", None)
        if not ui or ui.get("lang") != self.lang:
            return False
        tree = getattr(self, "tree", None)
        try:
            if tree is None or not tree.winfo_exists():
                return False
            if not ui["parent"].winfo_exists():
                return False
        except tk.TclError:
            return False

        sec = self.current_section
        # 顶部结构随分组变化的地方一律走重建，避免复用出半新半旧的状态：
        #   · 返回按钮：只在该显示而没有时才会出现差异
        #   · 后端从属提示条：只在图形类分组出现，出现/消失都改变控件层级
        if sec and ui.get("back") is None:
            return False
        if ui.get("backend_bar") != bool(
                navmeta.BACKEND_SECTIONS.get(sec) if sec else False):
            return False

        # 真正需要变的只有标题文字，就地改即可
        try:
            ui["title"].configure(
                text=self.sec_name(sec) if sec else self.t("list_all_sections"))
        except tk.TclError:
            return False

        self._refill_list_reuse()
        return True

    def _refill_list_reuse(self) -> None:
        """在已有控件上重填列表：清空行、更新空态提示、重算列宽。"""
        self.tree.delete(*self.tree.get_children())
        self._fill_tree()
        self._render_list_hint_if_empty()
        self._apply_tree_columns(refill=False)

    def _tree_rows_fit(self) -> int:
        """列表区实际能放下多少行。

        不能写死 height=20：窗口矮时（真机 1280x852）会撑破布局，
        把「设置详情」挤出屏幕；高时又浪费空间。按容器真实高度除以行高算。
        """
        row_h = getattr(self, "_row_height", 28) or 28
        try:
            host = getattr(self, "_tree_wrap", None) or self.list_host
            avail_h = host.winfo_height()
            if avail_h <= 1:
                avail_h = self.root.winfo_height()
            # 减去表头高度与少量边距
            head_h = row_h + 6
            n = int(max(3, (avail_h - head_h)) // row_h)
            return max(3, min(40, n))
        except Exception:  # noqa: BLE001
            return 12

    def _render_list_hint_if_empty(self) -> None:
        """当前分组一行都没有时，在列表下方给出缘由与出口。"""
        try:
            if self.tree is None or not self.tree.winfo_exists():
                return
            # 有内容（或正在搜索）时恢复列表的正常伸展，否则空态改过的布局会留下。
            # 注意：本方法是 after_idle 调度的，此时 self.rows 可能还是上一组的旧值；
            # 真正的判据是表格里现在到底有没有行（tree.get_children()）。
            # 曾经这里只看 self.rows，导致切到有内容的分组后仍保持空态的
            # height=3 / expand=False，表格被压成一条缝（真机 1280x852 实测）。
            has_rows = bool(self.tree.get_children())
            if has_rows or (self.search_var.get() or "").strip():
                try:
                    self.tree.configure(height=self._tree_rows_fit())
                    if getattr(self, "_tree_wrap", None) is not None:
                        self._tree_wrap.pack_configure(expand=True, fill="both")
                except Exception:  # noqa: BLE001
                    pass
                return
            host = getattr(self, "_list_hint_host", None)
            if host is None or not host.winfo_exists():
                return
            for w in host.winfo_children():
                w.destroy()
            sec = self.current_section
            if not sec:
                return
            n_tot = len(self.res.schema.get("sections", {}).get(sec, []))
            n_vis, why = self._section_visible_count(sec)
            if why != "advanced":
                return
            # 空表格会白占一大片高度、把提示条顶到屏幕外：把列表区收成固定高度，
            # 让「为什么没有内容 + 去哪里看」直接出现在视线里。
            try:
                # 空态只留表头 + 一点点高度，把提示条顶到视线里。
                # 不写死像素：行高随字体/缩放变化，写死会在 1.0 缩放下裁掉表头。
                self.tree.configure(height=2)
                if getattr(self, "_tree_wrap", None) is not None:
                    self._tree_wrap.pack_configure(expand=False, fill="x")
            except Exception:  # noqa: BLE001
                pass
            bar = tk.Frame(host, background=PALETTE["surface_alt"],
                           highlightbackground=PALETTE["border_strong"],
                           highlightthickness=1)
            bar.pack(fill="x", pady=(6, 0))
            tk.Label(bar, text="⊘", font=(self.icon_font, self.ui_base + 1),
                     width=2, anchor="center", background=PALETTE["surface_alt"],
                     foreground=PALETTE["primary"]).pack(side="left", padx=(8, 6))
            inner = tk.Frame(bar, background=PALETTE["surface_alt"])
            inner.pack(side="left", fill="x", expand=True, pady=6)
            tk.Label(inner, text=self.t("list_all_advanced", n=n_tot),
                     background=PALETTE["surface_alt"], foreground=PALETTE["deep"],
                     font=(self.ui_font, self.ui_base), anchor="w", justify="left",
                     wraplength=760).pack(anchor="w")
            tk.Label(inner, text=self.t("list_all_advanced_hint"),
                     background=PALETTE["surface_alt"], foreground=PALETTE["primary_dark"],
                     font=(self.ui_font, max(8, self.ui_base - 1)), anchor="w",
                     justify="left", wraplength=760).pack(anchor="w", pady=(2, 0))
            tk.Button(bar, text=self.t("btn_go_developer"),
                      command=lambda: self.select_nav("developer"),
                      relief="flat", borderwidth=0, cursor="hand2",
                      background=PALETTE["primary"], foreground=PALETTE["text_inverse"],
                      activebackground=PALETTE["primary_dark"],
                      activeforeground=PALETTE["text_inverse"],
                      font=(self.ui_font, self.ui_base),
                      padx=12, pady=3).pack(side="right", padx=(8, 10))
        except Exception:  # noqa: BLE001
            pass

    def _on_tree_configure(self, event=None) -> None:
        """窗口/容器尺寸变化时重算列宽（防抖，避免拖动时频繁重排）。"""
        if self.tree is None:
            return
        if self._col_job is not None:
            try:
                self.root.after_cancel(self._col_job)
            except Exception:
                pass
        self._col_job = self.root.after(80, self._apply_tree_columns)

    def _text_width(self, text: str, bold: bool = False) -> int:
        """用当前 UI 字体实测一段文本的像素宽度（受 tk scaling 影响）。"""
        try:
            from tkinter import font as tkfont
            f = tkfont.Font(root=self.root, family=self.ui_font,
                            size=self.ui_base, weight="bold" if bold else "normal")
            return int(f.measure(text))
        except Exception:  # noqa: BLE001
            return len(text) * 8  # 兜底估算

    def _apply_tree_columns(self, refill: bool = True) -> None:
        """按 Treeview 实际可用宽度分配四列，保证「已修改」列始终可见。

        列宽不能写死：高 DPI（tk scaling 1.5/2.0）下同样的字号会占用
        更宽的像素，「已修改」这类固定列会被裁掉。这里一律按字体实测宽度
        推算最小需求，再把剩余空间分配给可伸缩的两列。
        """
        self._col_job = None
        if self.tree is None:
            return
        # 用 Treeview 自身宽度最可靠；尚未布局时回退到容器/主区估算
        avail = self.tree.winfo_width()
        if avail <= 1:
            avail = self.list_host.winfo_width()
        if avail <= 1:
            avail = max(400, self._main_width() - 20)

        pad = 16  # 单元格左右内边距合计
        # 星标列：只需容纳一个符号 + 内边距
        star_w = max(26, self._text_width("✳") + pad)
        # 标记列：按表头文字（粗体）实测，保证「已修改」/「Modified」不截断
        head = self.t("col_modified")
        mark_w = max(44, self._text_width(head, bold=True) + pad)
        # 可伸缩列的可读下限
        # 设置项名的可读下限：按**本组实际最长键名**实测，而不是固定样例字符串。
        # 固定样例会让含 d3d12_allow_variable_refresh_rate_an 这类超长键名的组
        # 被截断到认不出来。
        # 表头文字也要能完整显示 —— 真机 1.0 缩放下「中文名」被截成「中文名|」，
        # 就是只算了内容宽度、没算表头。粗体表头比正文宽，按粗体量。
        longest_key = max((r["key"] for r in self.rows), key=len, default="")
        key_min = max(140, self._text_width(longest_key) + pad,
                      self._text_width(self.t("col_key"), bold=True) + pad)
        # 当前值列的兜底下限：只保证不塌陷，不按任何枚举文字去撑宽。
        # 之前用 "Auto (Default)"（158px）当基准，导致「关」「开」这类短值组
        # 也被撑到 158px，白占一大片。真实需求由下面的 val_need 按内容实测得出。
        val_min = max(70, self._text_width(self.t("col_value"), bold=True) + pad)
        # 「当前值」列按本组实际值实测 —— 有的组几乎全是「关」「开」（几十像素就够），
        # 有的组是「Interlaced (Default)」这类长枚举。按实测分配才不会让短值组
        # 白占一大片、把「中文名」列挤窄。上限受 val_min 的下限保护。
        val_need = val_min
        try:
            for r in self.rows:
                w = self._text_width(self.format_display(r["key"], r["type"])) + pad
                if w > val_need:
                    val_need = w
        except Exception:  # noqa: BLE001
            val_need = val_min
        val_need = min(val_need, max(val_min, int(avail * 0.30)))
        # 「说明」列（中文版专有）：按当前列表里最长中文名实测。
        # 上限放宽到 260 —— 原先 180 会截断「自定义内部显示分辨率 X」这类长中文名。
        brief_min = 70
        if self.brief_visible:
            longest = max((self.res.brief(self.lang, r["key"]) for r in self.rows),
                          key=len, default="")
            head_brief = self._text_width(self.t("col_brief"), bold=True) + pad
            brief_min = max(70, head_brief, min(260, self._text_width(longest) + pad))

        # 纵向滚动条是叠在 Treeview 之上的（同一父容器内、同宽），
        # 因此真正能画列的宽度 = 控件宽度 − 滚动条宽度。这里必须扣干净，
        # 否则最后一列会被滚动条盖住 —— 正是「已修改」列显示不全的原因。
        sb_w = 0
        try:
            for sb in self.tree.master.winfo_children():
                if isinstance(sb, ttk.Scrollbar) and "vertical" in str(sb.cget("orient")):
                    sb_w = max(sb_w, int(sb.winfo_reqwidth()))
        except Exception:  # noqa: BLE001
            sb_w = 0
        if sb_w <= 0:
            sb_w = self._tree_sb_w
        avail = max(300, avail - sb_w - 2)

        # 剩余空间按用户的四列分级分配：
        #   「设置项名」与「中文名」并列第一宽（两者等宽）
        #   「当前值」与「已修改」并列第二宽（两者等宽）
        # 两条硬规则：
        #   ① 设置项名必须完整显示本组最长键名，绝不截断；
        #   ② 总宽贴合内容，不强行撑满容器——否则短内容组（如账号区域）
        #      会出现大片空白，四列都被拉得虚胖。
        rest = avail - star_w - mark_w
        # 第二级：当前值 = 已修改。取「已修改」表头宽与最长值实测宽的较大者。
        # 但要给设置项名让路：键名列必须先拿到 key_min，剩下的才轮到当前值。
        # 否则长值组（如「显示输出」有 0.20000000298023224）会把键名挤到截断。
        key_reserve = key_min if self.brief_visible else min(key_min, rest)
        budget_for_val = max(0, rest - key_reserve - (80 if self.brief_visible else 0))
        val_need_real = max(mark_w, val_need)
        val_w = max(70, min(val_need_real, budget_for_val))
        rest -= val_w
        # 第一级：设置项名与中文名并列等宽。
        # 目标宽度 = 两列需求的较大者，这样两列必然同宽、且都不会截断。
        # 唯一例外：该宽度超过可用宽的一半时（长键名组或窄窗口），才允许不等宽，
        # 此时优先保设置项名（键名截断就没法辨识，中文名截断仍看得懂）。
        if self.brief_visible:
            # 键名列先无条件拿够最长键名宽度（这是硬要求）
            key_w = min(key_min, rest)
            brief_w = max(80, min(brief_min, rest - key_w))
            # 两列都不紧张时取等宽；任一不足则维持上面的优先分配
            need = max(key_min, brief_min)
            if need <= rest // 2 and rest - need >= need:
                key_w = brief_w = need
            elif key_w + brief_w > rest:
                # 合计超了：从中文名扣（保底 80），仍不够才动键名列
                brief_w = max(80, rest - key_w)
                if key_w + brief_w > rest:
                    key_w = max(0, rest - brief_w)
        else:
            brief_w = 0
            key_w = min(key_min, rest)
        if brief_w < 0:
            brief_w = 0

        # 总宽不得超过可用宽（超了就压缩）；有余量也不回填，保持贴合内容。
        total = star_w + key_w + brief_w + val_w + mark_w
        if total > avail and total > 0:
            over = total - avail
            # 压缩顺序：中文名 → 当前值 → 设置项名（设置项名最后动、且守 key_min）
            for attr, floor in (("brief_w", 80), ("val_w", 70), ("key_w", key_min)):
                if over <= 0:
                    break
                cur = {"brief_w": brief_w, "val_w": val_w, "key_w": key_w}[attr]
                cut = min(over, max(0, cur - floor))
                if attr == "brief_w":
                    brief_w -= cut
                elif attr == "val_w":
                    val_w -= cut
                else:
                    key_w -= cut
                over -= cut

        # stretch 必须关掉：Tk 会自动把「剩余空间」再分给 stretch=True 的列，
        # 从而覆盖掉我们算好的 width，让总和重新涨回去、把最后一列顶出可视区。
        # 各列宽度全部由本方法精确控制。
        # minwidth 必须与 width 一致：minwidth 大于 width 时 Tk 会强制拉到 minwidth，
        # 把「按内容贴合」的结果重新撑胖。
        # 无条件设全五列：任何一次跳过都可能残留上一组的宽度，
        # 列宽越界后极难自查（曾试过「没变就跳过」的短路，反而引入越界 bug）。
        # 各列宽度全部由本方法精确控制。
        # minwidth 必须与 width 一致：minwidth 大于 width 时 Tk 会强制拉到 minwidth，
        # 把「按内容贴合」的结果重新撑胖。
        self.tree.column("star", width=star_w, minwidth=star_w, anchor="center", stretch=False)
        self.tree.column("key", width=key_w, minwidth=key_w, anchor="w", stretch=False)
        self.tree.column("brief", width=brief_w, minwidth=brief_w, anchor="w", stretch=False)
        self.tree.column("value", width=val_w, minwidth=val_w, anchor="w", stretch=False)
        self.tree.column("modified", width=mark_w, minwidth=mark_w, anchor="center", stretch=False)
        self._last_avail = avail

        if refill:
            self._fill_tree()

    def _tooltip_text(self, iid: str) -> str:
        """Treeview 悬停回调：返回该行的说明文本。"""
        row = next((r for r in self.rows if r["iid"] == iid), None)
        if not row:
            return ""
        key = row["key"]
        desc = self.res.describe(self.lang, key)
        head = f"{key}   ({self.sec_name(row['section'])})"
        default = self.dict_default(key)
        if default is not None:
            head += f"\n{self.t('detail_default')}: {self.format_display(key, row['type'])}"
        return f"{head}\n\n{desc}" if desc else head

    def dict_default(self, key: str) -> str | None:
        return self.defaults.get(key) if self.defaults else None

    def _fill_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        if not self.doc or not self.tree.winfo_exists():
            return

        query = (self.search_var.get() or "").strip().lower()
        modified_only = not self.filter_all_var.get()
        entries = self.res.schema.get("entries", [])
        if not entries:
            entries = [{"key": k, "section": self.doc.get_section(k),
                        "value_type": "string", "comment": ""} for k in self.doc.keys()]

        allowed = None
        if not query:
            allowed = set(self.visible_sections(self.active_nav))

        # 依从过滤：只对当前后端有意义的分支项（搜索时不隐藏，避免搜不到）
        vals = self._cfg_values() if not query else None

        for e in entries:
            key = e["key"]
            sec = e.get("section") or ""
            if key not in self.doc.index:
                continue
            # 后端专属项可额外出现在对应后端分组下（见 navmeta.DEPENDENT_KEYS）
            extra = navmeta.also_in_section(key)
            eff_sec = extra if (self.current_section == extra) else sec
            if allowed is not None and sec not in allowed and eff_sec not in allowed:
                continue
            if vals is not None and not navmeta.key_visible(vals, key):
                continue
            if self.current_section and sec != self.current_section and \
                    eff_sec != self.current_section:
                continue
            if not query and not self.show_advanced and e.get("advanced") and \
                    self.active_nav != "developer":
                continue
            if modified_only and not self.is_modified(key):
                continue
            if query:
                hay = (f"{key}\n{sec}\n{self.res.describe(self.lang, key)}\n"
                       f"{self.res.brief(self.lang, key)}").lower()
                if query not in hay:
                    continue

            vtype = e.get("value_type", "string")
            mark = self.t("modified_mark") if self.is_modified(key) else ""
            feat = "✳" if key in navmeta.FEATURED_KEYS else ""
            tags = ("featured",) if feat else ()
            bname = self.res.brief(self.lang, key) if self.brief_visible else ""
            iid = self.tree.insert("", "end", tags=tags,
                                   values=(feat, key, bname,
                                           self.format_display(key, vtype), mark))
            self.rows.append({"iid": iid, "key": key, "section": eff_sec,
                              "type": vtype, "entry": e})

        if query:
            self.set_status(self.t("status_search_result", n=len(self.rows)))
        else:
            self.set_status(self.t("status_showing", shown=len(self.rows),
                                   total=self.res.schema.get("total", len(entries))))

        if self.selected_key:
            for r in self.rows:
                if r["key"] == self.selected_key:
                    self.tree.selection_set(r["iid"])
                    self.tree.see(r["iid"])
                    break

    def focus_editor(self) -> None:
        if self.editor_widget is not None:
            try:
                self.editor_widget.focus_set()
            except tk.TclError:
                pass

    def _on_tree_double(self, event) -> None:
        """双击：选中项直接聚焦编辑器；空白处则弹出说明。"""
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.on_row_select()
        self.focus_editor()

    def _on_tree_press(self, event) -> None:
        """触摸屏长按唤出说明（鼠标用户按下不动同样触发）。"""
        iid = self.tree.identify_row(event.y)
        self._press_iid = iid or None
        if iid:
            self._press_after = self.tree.after(650, lambda: self._show_desc_for(iid, event))

    def _on_tree_release(self, _event=None) -> None:
        aid = getattr(self, "_press_after", None)
        if aid is not None:
            try:
                self.tree.after_cancel(aid)
            except (tk.TclError, ValueError):
                pass
            self._press_after = None

    def _show_desc_for(self, iid: str, _event=None) -> None:
        row = next((r for r in self.rows if r["iid"] == iid), None)
        if not row:
            return
        self.selected_key = row["key"]
        self.tree.selection_set(iid)
        self.render_detail()
        self.show_desc_window()

    def format_display(self, key: str, vtype: str) -> str:
        raw = self.doc.get(key)
        if raw is None:
            return "—"
        if vtype == "bool":
            return self.t("value_true_short") if raw == "true" else self.t("value_false_short")
        if vtype == "string":
            inner = raw.strip()
            if inner.startswith('"') and inner.endswith('"'):
                inner = inner[1:-1]
            return inner if inner else self.t("hint_string_empty")
        # [XConfig] 的国家/语言：列表里也显示可读名称，光看数字没法选
        if key in self.res.xconfig:
            name = self.res.lookup(key, raw, self.lang)
            if name != raw:
                return f"{name} ({raw})"
        return raw

    # ------------------------------------------------------------ 详情与编辑

    def on_row_select(self, _event=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        row = next((r for r in self.rows if r["iid"] == sel[0]), None)
        if not row:
            return
        self.selected_key = row["key"]
        self.render_detail()

    def render_detail(self) -> None:
        for child in self.editor_holder.winfo_children():
            child.destroy()
        self.editor_widget = None
        self.editor_var = None

        key = self.selected_key
        if not key or not self.doc or key not in self.doc.index:
            self.detail_meta.configure(text=self.t("detail_hint"))
            self.btn_revert.state(["disabled"])
            self.btn_desc.state(["disabled"])
            return

        row = next((r for r in self.rows if r["key"] == key), None)
        vtype = row["type"] if row else "string"
        sec = self.doc.get_section(key) or ""

        meta = (f"{self.sec_name(sec)}  ·  {key}  ·  {self.t('detail_type')}: {vtype}"
                f"  ·  {self.t('detail_default')}: "
                f"{self.format_display(key, vtype)}")
        if self.is_modified(key):
            meta += f"  ·  {self.t('detail_modified')}"
        self.detail_meta.configure(text=meta)
        self.btn_desc.state(["!disabled"])

        raw = self.doc.get(key)

        if vtype == "bool":
            var = tk.BooleanVar(value=(raw == "true"))
            cb = ttk.Checkbutton(self.editor_holder,
                                 text=self.t("value_true") if var.get() else self.t("value_false"),
                                 variable=var)
            cb.configure(command=lambda v=var, w=cb: self._bool_changed(v, w))
            cb.pack(side="left")
            self.editor_var = var
            self.editor_widget = cb
        else:
            var = tk.StringVar(value=self._unquote(raw))
            entry = ttk.Entry(self.editor_holder, textvariable=var, width=40)
            entry.pack(side="left", fill="x", expand=True)
            entry.bind("<Return>", lambda e: self.apply_editor())
            entry.bind("<FocusOut>", lambda e: self.apply_editor())
            apply_btn = ttk.Button(self.editor_holder, text=self.t("btn_apply"),
                                   command=self.apply_editor)
            apply_btn.pack(side="left", padx=(6, 0))
            self.editor_var = var
            self.editor_widget = entry

            choices = row["entry"].get("choices") if row else None
            if choices:
                ttk.Label(self.editor_holder, text=self.t("label_choices"),
                          style="Blurb.TLabel").pack(side="left", padx=(8, 4))
                combo = ttk.Combobox(self.editor_holder, textvariable=var, values=choices,
                                     width=14, state="readonly")
                combo.pack(side="left")
                combo.bind("<<ComboboxSelected>>", lambda e: self.apply_editor())
            elif row and row["entry"].get("key") in self.res.xconfig:
                # [XConfig] 的国家/语言：数值本身没有意义，渲染成可读名称下拉框。
                self._build_lookup_editor(row["entry"].get("key"), var)

        self.btn_revert.state(["!disabled"] if self.is_modified(key) else ["disabled"])

    def _build_lookup_editor(self, key: str, var) -> None:
        """给 [XConfig] 的国家/语言做「名称 → 数值」下拉框。

        编辑框里显示可读名称（如 `中国 (20)`），但写回配置文件时必须落成
        数字（`20`）。因此在选择时把名称翻回数值，再刷新编辑框显示。
        """
        labels, values = self.res.choice_labels(key, self.lang)
        if not labels:
            return
        ttk.Label(self.editor_holder, text=self.t("label_choices"),
                  style="Blurb.TLabel").pack(side="left", padx=(8, 4))
        cur = self.format_display(key, self._cfg_values().get(key, ""))
        shown = self.res.lookup(key, cur, self.lang)
        label = next((lab for lab in labels if lab == shown or lab.startswith(f"{shown} (")), shown)
        combo = ttk.Combobox(self.editor_holder, values=labels, width=22, state="readonly")
        combo.set(label)
        combo.pack(side="left")

        def on_pick(_event=None) -> None:
            pick = combo.get()
            try:
                idx = labels.index(pick)
            except ValueError:
                return
            var.set(values[idx])          # 编辑框持有真实数值
            self.apply_editor()           # 立即写入文档
            self._refresh_editor_display(key)

        combo.bind("<<ComboboxSelected>>", lambda e: on_pick())
        self._lookup_combo = combo

    def _refresh_editor_display(self, key: str) -> None:
        """把编辑框内容刷新成可读名称（国家/语言专用）。"""
        combo = getattr(self, "_lookup_combo", None)
        if combo is None or self.selected_key != key:
            return
        cur = self._cfg_values().get(key, "")
        name = self.res.lookup(key, self.format_display(key, cur), self.lang)
        labels, _ = self.res.choice_labels(key, self.lang)
        label = next((lab for lab in labels if lab.startswith(f"{name} (")), name)
        try:
            combo.set(label)
        except tk.TclError:
            pass

    def show_desc_window(self) -> None:
        """弹出完整说明窗口（触摸屏 / 长文本场景）。"""
        key = self.selected_key
        if not key:
            return
        desc = self.res.describe(self.lang, key)
        win = tk.Toplevel(self.root)
        win.title(f"{key} — {self.t('detail_desc')}")
        win.geometry("640x460")
        win.transient(self.root)
        frame = ttk.Frame(win, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=f"{self.sec_name(self.doc.get_section(key) or '')}  ·  {key}",
                  style="Section.TLabel").pack(anchor="w", pady=(0, 6))
        txt = tk.Text(frame, wrap="word", relief="solid", borderwidth=1)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", desc)
        txt.configure(state="disabled")
        ttk.Button(frame, text=self.t("btn_close"),
                   command=win.destroy).pack(anchor="e", pady=(8, 0))
        win.bind("<Escape>", lambda e: win.destroy())

    def _bool_changed(self, var: tk.BooleanVar, widget) -> None:
        widget.configure(text=self.t("value_true") if var.get() else self.t("value_false"))
        self.apply_editor()

    @staticmethod
    def _unquote(raw: str | None) -> str:
        if raw is None:
            return ""
        s = raw.strip()
        if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
            s = s[1:-1].replace('\\"', '"').replace("\\\\", "\\")
        return s

    def apply_editor(self) -> None:
        key = self.selected_key
        if not key or not self.doc or self.editor_var is None:
            return
        row = next((r for r in self.rows if r["key"] == key), None)
        vtype = row["type"] if row else "string"
        val = self.editor_var.get()
        try:
            if vtype == "bool":
                self.doc.set(key, bool(val), "bool")
                self._bump_doc_version()
            elif vtype == "int":
                self.doc.set(key, int(str(val).strip() or "0"), "int")
                self._bump_doc_version()
            elif vtype == "float":
                self.doc.set(key, float(str(val).strip() or "0"), "float")
                self._bump_doc_version()
            else:
                self.doc.set(key, val, "string")
                self._bump_doc_version()
        except (ValueError, TypeError) as exc:
            messagebox.showerror(self.t("dlg_error_title"), self.t("err_invalid_value", err=exc))
            return

        for r in self.rows:
            if r["key"] == key and self.tree.exists(r["iid"]):
                self.tree.set(r["iid"], "value", self.format_display(key, vtype))
                self.tree.set(r["iid"], "modified",
                              self.t("modified_mark") if self.is_modified(key) else "")
                break
        self.update_modified_count()
        self.btn_revert.state(["!disabled"] if self.is_modified(key) else ["disabled"])

        # 改动了依从开关（如 gpu）会让另一后端的分组与专属项出现/消失，
        # 此时必须整段重建，否则用户看到的是过期的可见性。
        if navmeta.affects_visibility(key):
            self.render_rows()
            return
        if self.current_section:
            self._refresh_card_badges()

    def _refresh_card_badges(self) -> None:
        """就地刷新分组卡片的角标配色（已修改 / 选中 / 空组）。

        原先这里调 render_rows() 整片重建：真机实测每次改一个设置就要多花
        约 700ms。卡片上的数字（可见项数）在改普通设置时并不变，变的只是
        「有没有被改过」对应的颜色，改一个 Label 的 fg 就够了。
        """
        badges = getattr(self, "card_badges", None)
        if not badges:
            self.render_rows()
            return
        for section, (cd, card_bg, empty) in list(badges.items()):
            if not cd.winfo_exists():
                continue
            active = self.current_section == section
            modified = any(self.is_modified(k)
                           for k in self._keys_of_section(section))
            try:
                cd.configure(
                    foreground=PALETTE["warning"] if empty else
                    (PALETTE["modified"] if modified else
                     (PALETTE["primary_dark"] if active else PALETTE["text_muted"])),
                    font=(self.ui_font, max(8, self.ui_base - 1),
                          "bold" if active else "normal"))
            except tk.TclError:
                pass

    def revert_selected(self) -> None:
        key = self.selected_key
        if not key or not self.doc or not self.compare or key not in self.compare.index:
            return
        vtype = next((r["type"] for r in self.rows if r["key"] == key), "string")
        raw = self.compare.get(key)
        if vtype == "bool":
            self.doc.set(key, raw == "true", "bool")
            self._bump_doc_version()
        elif vtype in ("int", "float"):
            self.doc.set(key, raw, vtype)
            self._bump_doc_version()
        else:
            self.doc.set(key, self._unquote(raw), "string")
            self._bump_doc_version()
        self.render_rows()
        self.render_detail()

    def restore_defaults(self) -> None:
        if not self.doc or not self.defaults:
            return
        if not messagebox.askyesno(self.t("dlg_warn_title"), self.t("dlg_confirm_restore_all")):
            return
        types = {e["key"]: e.get("value_type", "string")
                 for e in self.res.schema.get("entries", [])}
        for key, raw in self.defaults.items():
            if raw is None or key not in self.doc.index:
                continue
            vt = types.get(key, "string")
            if vt == "bool":
                self.doc.set(key, raw == "true", "bool")
                self._bump_doc_version()
            elif vt in ("int", "float"):
                self.doc.set(key, raw, vt)
                self._bump_doc_version()
            else:
                self.doc.set(key, self._unquote(raw), "string")
                self._bump_doc_version()
        self.render_rows()
        self.render_detail()

    def apply_preset(self, preset_id: str) -> None:
        """套用掌机预设：列出将被改动的项，确认后再写入。"""
        if not self.doc:
            messagebox.showwarning(self.t("dlg_warn_title"), self.t("empty_body"))
            return
        preset = next((p for p in navmeta.DEVICE_PRESETS if p["id"] == preset_id), None)
        if not preset:
            return

        types = {e["key"]: e.get("value_type", "string")
                 for e in self.res.schema.get("entries", [])}

        # 汇总改动（只列真正会变化的项）
        changes = []
        for key, newval in preset["values"].items():
            if key not in self.doc.index:
                continue
            vt = types.get(key, "string")
            cur = self.doc.get(key)
            cur_disp = self.format_display(key, vt)
            if vt == "bool":
                new_disp = self.t("val_on") if newval else self.t("val_off")
                same = (str(cur).lower() == "true") == bool(newval)
            else:
                new_disp = str(newval)
                same = str(cur).strip().strip('"') == str(newval)
            if not same:
                changes.append((key, cur_disp, new_disp, vt, newval))

        if not changes:
            messagebox.showinfo(self.t("dlg_info_title"), self.t("preset_no_change"))
            return

        pname = preset["name"].get(self.lang) or preset["name"]["en"]
        lines = [self.t("preset_confirm_head", name=pname), ""]
        for key, cur_disp, new_disp, _vt, _nv in changes[:14]:
            lines.append(f"  {key}:  {cur_disp}  →  {new_disp}")
        if len(changes) > 14:
            lines.append(f"  … {self.t('preset_more', n=len(changes) - 14)}")
        lines.append("")
        lines.append(self.t("preset_confirm_tail"))

        if not messagebox.askyesno(self.t("menu_presets"), "\n".join(lines)):
            return

        for key, _cd, _nd, vt, newval in changes:
            if vt == "bool":
                self.doc.set(key, bool(newval), "bool")
                self._bump_doc_version()
            elif vt in ("int", "float"):
                self.doc.set(key, newval, vt)
                self._bump_doc_version()
            else:
                self.doc.set(key, str(newval), "string")
                self._bump_doc_version()

        self.render_rows()
        self.render_detail()
        self.set_status(self.t("preset_applied", n=len(changes)))

    # ------------------------------------------------------------ 搜索

    def _toggle_placeholder(self, *_args) -> None:
        pass

    def _on_search_key(self, event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        # 搜索只过滤列表，卡片区的分组与计数不受影响
        self.render_rows(cards=False)

    def on_search(self) -> None:
        self.render_rows(cards=False)

    def clear_search(self) -> None:
        self.search_var.set("")
        self.render_rows(cards=False)

    def focus_search(self) -> None:
        self.search_entry.focus_set()

    # ------------------------------------------------------------ 开关

    def toggle_backup(self) -> None:
        self.auto_backup = bool(self.backup_var.get())
        self.store.set("auto_backup", self.auto_backup)

    def toggle_advanced(self) -> None:
        self.show_advanced = bool(self.advanced_var.get())
        self.store.set("show_advanced", self.show_advanced)
        if not self.show_advanced and self.active_nav == "developer":
            self.active_nav = "common"
        self.render_all()

    # ------------------------------------------------------------ 帮助

    def show_about(self) -> None:
        messagebox.showinfo(self.t("menu_about"),
                            self.t("about_body", total=self.res.schema.get("total", 0),
                                   path=str(self.config_path or "—"), version=APP_VERSION))

    def show_shortcuts(self) -> None:
        messagebox.showinfo(self.t("menu_shortcuts"), self.t("shortcuts_body"))

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def _register_tip(self, tip) -> None:
        """登记提示框实例，便于退出时统一取消其待弹出的 after 任务。

        导航条目与分组卡片每次重建都会生成新实例，因此这里只保留
        仍然存活的那些，避免列表无界增长。
        """
        bucket = getattr(self, "_tips", None)
        if bucket is None:
            bucket = self._tips = []
        # 先剔除已随父控件销毁的旧实例
        alive = []
        for t in bucket:
            w = getattr(t, "widget", None)
            try:
                if w is not None and w.winfo_exists():
                    alive.append(t)
            except Exception:  # noqa: BLE001
                pass
        alive.append(tip)
        self._tips = alive

    def _cancel_pending_jobs(self) -> None:
        """销毁窗口前取消所有待执行的 after 回调。

        否则回调会在窗口已销毁后触发，Tk 报
        `invalid command name "..._apply_sash"` 之类的错误。
        """
        for attr in ("_sash_job", "_col_job", "_tip_job", "_press_job"):
            job = getattr(self, attr, None)
            if job is not None:
                try:
                    self.root.after_cancel(job)
                except Exception:  # noqa: BLE001
                    pass
                setattr(self, attr, None)
        # 提示框的 after 任务挂在各自控件上，需逐个取消
        for t in getattr(self, "_tips", []):
            try:
                t.cancel()
            except Exception:  # noqa: BLE001
                pass
        self._tips = []

    def on_quit(self) -> None:
        if self.has_changes() and not messagebox.askyesno(
                self.t("dlg_warn_title"), self.t("ask_quit_unsaved")):
            return
        self.store.save()
        self._cancel_pending_jobs()
        self.root.destroy()


def main() -> int:
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        sys.stderr.write(
            "无法连接显示服务器（Wayland/X11 均不可用）。\n"
            f"详情：{exc}\n探测结果：{DISPLAY_INFO}\n")
        return 2
    ConfigToolApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
