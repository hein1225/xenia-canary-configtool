#!/usr/bin/env python3
"""生成应用图标（纯标准库，无第三方依赖）。

产出 PNG 多尺寸图标，用于 AppImage 的 .DirIcon 与桌面集成。
设计：深色圆角底 + 模拟器手柄抽象图形 + 滑块/齿轮元素，呼应"配置工具"。
"""
from __future__ import annotations

import struct
import zlib
from pathlib import Path

# 配色（深色主题，掌机友好对比度）
BG_TOP = (0x1E, 0x2A, 0x38)
BG_BOTTOM = (0x0F, 0x16, 0x1F)
ACCENT = (0x3D, 0xD5, 0x98)      # 主强调色（青绿）
ACCENT_DIM = (0x2A, 0x9E, 0x71)
WHITE = (0xE8, 0xEF, 0xF4)
GREY = (0x5A, 0x6B, 0x7B)


class Canvas:
    """极简 RGBA 画布，带抗锯齿绘制。"""

    def __init__(self, size: int):
        self.size = size
        self.buf = bytearray(size * size * 4)

    def blend(self, x: int, y: int, color, alpha: float) -> None:
        if not (0 <= x < self.size and 0 <= y < self.size) or alpha <= 0:
            return
        i = (y * self.size + x) * 4
        a = min(1.0, alpha)
        for c in range(3):
            dst = self.buf[i + c]
            self.buf[i + c] = int(dst * (1 - a) + color[c] * a + 0.5)
        self.buf[i + 3] = max(self.buf[i + 3], int(255 * a))

    def fill_all(self, color) -> None:
        for y in range(self.size):
            for x in range(self.size):
                i = (y * self.size + x) * 4
                self.buf[i:i + 3] = bytes(color)
                self.buf[i + 3] = 255

    @staticmethod
    def _coverage(dist: float, edge: float) -> float:
        """用 1px 过渡带做抗锯齿：dist 为到边界的距离（内部为正）。"""
        return max(0.0, min(1.0, dist / edge + 0.5))

    def rounded_rect(self, x0, y0, x1, y1, radius, color, alpha=1.0, edge=1.0) -> None:
        for y in range(max(0, int(y0 - 2)), min(self.size, int(y1 + 3))):
            for x in range(max(0, int(x0 - 2)), min(self.size, int(x1 + 3))):
                cx = min(max(x + 0.5, x0 + radius), x1 - radius)
                cy = min(max(y + 0.5, y0 + radius), y1 - radius)
                d = radius - ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
                if d > -1.5:
                    self.blend(x, y, color, alpha * self._coverage(d, edge))

    def circle(self, cx, cy, r, color, alpha=1.0, edge=1.0) -> None:
        for y in range(max(0, int(cy - r - 2)), min(self.size, int(cy + r + 3))):
            for x in range(max(0, int(cx - r - 2)), min(self.size, int(cx + r + 3))):
                d = r - ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
                if d > -1.5:
                    self.blend(x, y, color, alpha * self._coverage(d, edge))

    def vertical_gradient_rounded(self, x0, y0, x1, y1, radius, c_top, c_bottom) -> None:
        h = max(1.0, y1 - y0)
        for y in range(max(0, int(y0 - 2)), min(self.size, int(y1 + 3))):
            t = min(1.0, max(0.0, (y - y0) / h))
            color = tuple(int(c_top[i] * (1 - t) + c_bottom[i] * t) for i in range(3))
            for x in range(max(0, int(x0 - 2)), min(self.size, int(x1 + 3))):
                cx = min(max(x + 0.5, x0 + radius), x1 - radius)
                cy = min(max(y + 0.5, y0 + radius), y1 - radius)
                d = radius - ((x + 0.5 - cx) ** 2 + (y + 0.5 - cy) ** 2) ** 0.5
                if d > -1.5:
                    self.blend(x, y, color, self._coverage(d, 1.0))

    def to_png(self) -> bytes:
        raw = b"".join(
            b"\x00" + bytes(self.buf[y * self.size * 4:(y + 1) * self.size * 4])
            for y in range(self.size)
        )
        return _png(self.size, self.size, raw)


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + tag + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))


def _png(w: int, h: int, raw: bytes) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def draw_icon(size: int) -> bytes:
    c = Canvas(size)
    S = size

    # 圆角底板
    m = S * 0.045
    c.vertical_gradient_rounded(m, m, S - m, S - m, S * 0.22, BG_TOP, BG_BOTTOM)

    # 手柄机身
    bx0, bx1 = S * 0.17, S * 0.83
    by0, by1 = S * 0.33, S * 0.69
    c.rounded_rect(bx0, by0, bx1, by1, S * 0.15, WHITE, alpha=0.93)

    # 左右握把
    c.circle(S * 0.19, S * 0.55, S * 0.115, WHITE, alpha=0.93)
    c.circle(S * 0.81, S * 0.55, S * 0.115, WHITE, alpha=0.93)

    # 左摇杆（强调色）
    c.circle(S * 0.335, S * 0.505, S * 0.072, ACCENT)
    c.circle(S * 0.335, S * 0.505, S * 0.037, BG_BOTTOM, alpha=0.85)

    # 右侧四键
    for dx, dy in ((-0.088, 0), (0.088, 0), (0, -0.088), (0, 0.088)):
        c.circle(S * (0.665 + dx), S * (0.505 + dy), S * 0.032, ACCENT_DIM)

    # 底部"滑块"三条：呼应配置调节
    for k, (yy, xx) in enumerate(((0.795, 0.30), (0.855, 0.50), (0.915, 0.70))):
        y = S * yy
        c.rounded_rect(S * 0.20, y - S * 0.019, S * 0.80, y + S * 0.019,
                       S * 0.019, GREY, alpha=0.75)
        knob_x = S * (xx + (0.06 if k == 1 else -0.04))
        c.circle(knob_x, y, S * 0.038, ACCENT)
        c.circle(knob_x, y, S * 0.017, BG_TOP, alpha=0.9)

    return c.to_png()


def main() -> int:
    out_dir = Path(__file__).resolve().parent.parent / "assets" / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256, 512]
    for s in sizes:
        data = draw_icon(s)
        (out_dir / f"xenia-canary-configtool-{s}.png").write_bytes(data)
        print(f"  ✓ {s}x{s}  ({len(data)} bytes)")
    # 主图标
    (out_dir / "xenia-canary-configtool.png").write_bytes(draw_icon(256))
    print(f"图标已生成到 {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
