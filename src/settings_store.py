#!/usr/bin/env python3
"""本工具自身的偏好设置持久化（与 xenia 配置无关）。

存放位置遵循 XDG 规范，SteamOS 上同样适用：
  $XDG_CONFIG_HOME/xenia-canary-configtool/settings.json
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

APP_ID = "xenia-canary-configtool"

DEFAULTS = {
    "language": "zh",        # 界面语言：zh / en
    "auto_backup": True,     # 保存前自动备份
    "show_advanced": False,  # 是否显示开发者选项
    "last_path": "",         # 上次打开的配置文件路径
    "window_geometry": "",   # 窗口位置尺寸
}


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / APP_ID


class SettingsStore:
    """轻量键值存储，写入采用原子替换避免损坏。"""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config_dir() / "settings.json"
        self.data = dict(DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            if self.path.is_file():
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    self.data.update({k: v for k, v in loaded.items() if k in DEFAULTS})
        except (OSError, ValueError):
            # 配置损坏时回落默认值，不影响启动
            self.data = dict(DEFAULTS)

    def get(self, key: str, default=None):
        return self.data.get(key, DEFAULTS.get(key, default))

    def set(self, key: str, value) -> None:
        self.data[key] = value

    def save(self) -> bool:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            return True
        except OSError:
            return False
