#!/usr/bin/env python3
"""轻量 Tooltip 组件（纯 Tkinter 实现，无第三方依赖）。

用于鼠标悬停时显示设置项的完整说明，从而把说明从常驻面板改为按需弹出，
为设置列表腾出横向空间。

掌机/触摸适配：同时支持鼠标悬停和长按（触摸屏无 hover 事件）。
"""
from __future__ import annotations

import tkinter as tk


class Tooltip:
    """鼠标悬停显示文本的浮动提示框。

    参数：
      widget      宿主控件
      text        提示内容（可后续用 set_text 更新）
      wraplength  换行宽度（像素）
      delay       延迟毫秒数，避免快速划过时闪烁
    """

    def __init__(self, widget: tk.Widget, text: str = "", wraplength: int = 460,
                 delay: int = 420, max_chars: int = 2000):
        self.widget = widget
        self.text = text
        self.wraplength = wraplength
        self.delay = delay
        self.max_chars = max_chars
        self._after_id: str | None = None
        self._tip: tk.Toplevel | None = None
        self._enabled = True

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        # 触摸屏无 hover：按下并保持一段时间即可唤出说明
        widget.bind("<ButtonPress-1>", self._on_press, add="+")
        widget.bind("<ButtonRelease-1>", self._on_release, add="+")

    # ---------------------------------------------------------- 公共接口

    def set_text(self, text: str) -> None:
        self.text = text or ""
        if self._tip is not None:
            self._hide()

    def enable(self, flag: bool = True) -> None:
        self._enabled = flag
        if not flag:
            self._hide()

    # ---------------------------------------------------------- 事件

    def _on_enter(self, _event=None) -> None:
        if not self._enabled or not self.text:
            return
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, _event=None) -> None:
        self._cancel()
        self._hide()

    # 触摸屏长按唤出（鼠标按下后停留同样生效，松手即消失）

    def _on_press(self, _event=None) -> None:
        if not self._enabled or not self.text:
            return
        self._cancel()
        self._press_id = self.widget.after(600, self._show)

    def _on_release(self, _event=None) -> None:
        pid = getattr(self, "_press_id", None)
        if pid is not None:
            try:
                self.widget.after_cancel(pid)
            except (tk.TclError, ValueError):
                pass
            self._press_id = None
        if self._tip is not None:
            self._hide()

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except (tk.TclError, ValueError):
                pass
            self._after_id = None

    # ---------------------------------------------------------- 显示

    def _show(self) -> None:
        self._after_id = None
        if self._tip is not None or not self.text:
            return
        # 窗口树可能已被销毁：此时直接放弃（否则 Tk 会抛 bad window path name）
        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx() + 24
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        except tk.TclError:
            return

        tip = tk.Toplevel(self.widget)
        tip.wm_overrideredirect(True)
        tip.wm_attributes("-topmost", True)
        try:
            tip.tk.call("wm", "attributes", tip._w, "-type", "tooltip")
        except tk.TclError:
            pass  # 非 X11 合成器可能不支持，忽略即可

        # 深色提示框，任何主题下都清晰
        frame = tk.Frame(tip, background="#2b2b2b", borderwidth=0)
        frame.pack(fill="both", expand=True)

        text = self.text
        if len(text) > self.max_chars:
            text = text[: self.max_chars] + "\n…"

        label = tk.Label(frame, text=text, justify="left", anchor="w",
                         background="#2b2b2b", foreground="#eee",
                         wraplength=self.wraplength, padx=10, pady=8)
        label.pack()

        tip.update_idletasks()
        try:
            w = tip.winfo_reqwidth()
            h = tip.winfo_reqheight()
        except tk.TclError:
            # 窗口树已销毁（例如程序退出时延后触发的 after 回调）
            self._tip = None
            return

        # 贴边时调整位置，避免提示框超出屏幕
        sw = tip.winfo_screenwidth()
        sh = tip.winfo_screenheight()
        if x + w > sw - 8:
            x = max(0, sw - w - 8)
        if y + h > sh - 8:
            y = max(0, self.widget.winfo_rooty() - h - 6)
        tip.wm_geometry(f"+{int(x)}+{int(y)}")

        self._tip = tip

    def _hide(self) -> None:
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None

    def cancel(self) -> None:
        """取消待弹出任务并隐藏提示框。窗口销毁前必须调用。"""
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except (tk.TclError, ValueError):
                pass
            self._after_id = None
        self._hide()


class TreeTooltip:
    """给 ttk.Treeview 的某一行提供悬停说明。

    Treeview 的行不是独立控件，只能绑定在整体上，用鼠标坐标反查行号。
    """

    def __init__(self, tree, provider, wraplength: int = 520, delay: int = 480):
        self.tree = tree
        self.provider = provider      # 回调：接收 iid，返回说明文本
        self.wraplength = wraplength
        self.delay = delay
        self._after_id: str | None = None
        self._tip: tk.Toplevel | None = None
        self._cur_iid: str | None = None

        tree.bind("<Motion>", self._on_motion, add="+")
        tree.bind("<Leave>", self._on_leave, add="+")
        tree.bind("<ButtonPress>", self._on_leave, add="+")
        # 滚轮/滚动时提示应消失，否则会错位
        tree.bind("<MouseWheel>", self._on_leave, add="+")
        tree.bind("<Button-4>", self._on_leave, add="+")
        tree.bind("<Button-5>", self._on_leave, add="+")

    def _row_at(self, event) -> str | None:
        try:
            iid = self.tree.identify_row(event.y)
            return iid or None
        except tk.TclError:
            return None

    def _on_motion(self, event) -> None:
        iid = self._row_at(event)
        if iid != self._cur_iid:
            self._cancel()
            self._hide()
            self._cur_iid = iid
            if iid:
                self._after_id = self.tree.after(self.delay, lambda: self._show(iid, event))
        elif iid and self._tip is not None:
            self._cancel()
            self._hide()
            self._after_id = self.tree.after(self.delay, lambda: self._show(iid, event))

    def _on_leave(self, _event=None) -> None:
        self._cancel()
        self._hide()
        self._cur_iid = None

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.tree.after_cancel(self._after_id)
            except (tk.TclError, ValueError):
                pass
            self._after_id = None

    def _show(self, iid: str, event) -> None:
        self._after_id = None
        if self._tip is not None:
            return
        text = self.provider(iid) or ""
        if not text.strip():
            return
        try:
            if not self.tree.winfo_exists():
                return
            x = self.tree.winfo_rootx() + min(event.x + 22, self.tree.winfo_width() - 60)
            y = self.tree.winfo_rooty() + event.y + 24
        except tk.TclError:
            return

        tip = tk.Toplevel(self.tree)
        tip.wm_overrideredirect(True)
        tip.wm_attributes("-topmost", True)
        frame = tk.Frame(tip, background="#2b2b2b")
        frame.pack(fill="both", expand=True)
        tk.Label(frame, text=text, justify="left", anchor="w",
                 background="#2b2b2b", foreground="#eee",
                 wraplength=self.wraplength, padx=10, pady=8).pack()

        tip.update_idletasks()
        w, h = tip.winfo_reqwidth(), tip.winfo_reqheight()
        sw, sh = tip.winfo_screenwidth(), tip.winfo_screenheight()
        if x + w > sw - 8:
            x = max(0, sw - w - 8)
        if y + h > sh - 8:
            y = max(0, self.tree.winfo_rooty() + event.y - h - 6)
        tip.wm_geometry(f"+{int(x)}+{int(y)}")
        self._tip = tip

    def _hide(self) -> None:
        if self._tip is not None:
            try:
                self._tip.destroy()
            except tk.TclError:
                pass
            self._tip = None

    def cancel(self) -> None:
        """取消待弹出任务并隐藏提示框。窗口销毁前必须调用。"""
        self._cancel()
        self._hide()
