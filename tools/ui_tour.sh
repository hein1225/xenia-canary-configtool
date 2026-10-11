#!/usr/bin/env bash
# 界面巡检：自动遍历关键视图并逐一截图，便于人工核对。
#
# 覆盖：各导航大类、分组进入、搜索、开发者选项过滤、双语切换。
set -uo pipefail

OUT="${1:-/workspace/code/xenia-canary-configtool/build/tour}"
mkdir -p "$OUT"
export DISPLAY=:99
xdpyinfo -display :99 >/dev/null 2>&1 || { Xvfb :99 -screen 0 1280x800x24 >/dev/null 2>&1 & sleep 2; }

cd /workspace/code/xenia-canary-configtool

shoot() {  # shoot <文件名> <说明>
    sleep "${3:-1.5}"
    import -display :99 -window root "$OUT/$1.png" 2>/dev/null && echo "  ✓ $1 — $2"
}

start_app() {
    python3 src/app.py >/tmp/tour_app.log 2>&1 &
    APP_PID=$!
    sleep 7
}

stop_app() {
    kill "$APP_PID" 2>/dev/null
    wait "$APP_PID" 2>/dev/null
}

click() { xdotool mousemove "$1" "$2" click 1 2>/dev/null; sleep 1.2; }

echo "=== 界面巡检（中文）==="
python3 -c "
import sys; sys.path.insert(0,'src')
from settings_store import SettingsStore
s=SettingsStore(); s.set('language','zh'); s.save()"
start_app

shoot "01-essentials" "常用设置（默认视图）"
click 200 212;  shoot "02-graphics"  "图形后端大类"
click 200 240;  shoot "03-system"    "系统与存储大类"
click 200 300;  shoot "04-storage"   "存储路径分组（已选）"
click 210 300;  shoot "05-back-all"  "退出分组回到全部"

# 搜索
xdotool mousemove 520 127 click 1; sleep 0.5
xdotool type --delay 60 "vulkan"; sleep 1.5
shoot "06-search-vulkan" "搜索 vulkan"
xdotool key ctrl+a; xdotool type --delay 60 "分辨率"; sleep 1.5
shoot "07-search-zh"     "中文搜索「分辨率」"

stop_app

echo
echo "=== 界面巡检（英文）==="
python3 -c "
import sys; sys.path.insert(0,'src')
from settings_store import SettingsStore
s=SettingsStore(); s.set('language','en'); s.save()"
start_app
shoot "08-en-essentials" "英文常用设置"
click 200 240; shoot "09-en-system" "英文系统与存储"
stop_app

python3 -c "
import sys; sys.path.insert(0,'src')
from settings_store import SettingsStore
s=SettingsStore(); s.set('language','zh'); s.save()"

echo
echo "截图目录: $OUT"
ls -1 "$OUT"
