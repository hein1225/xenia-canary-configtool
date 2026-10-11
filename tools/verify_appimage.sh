#!/usr/bin/env bash
# 验证 AppImage 能在隔离环境中独立运行。
#
# 手法：在容器里用 unshare 挂载一个空的 /usr（或退而求其次，用 PATH 隔离 +
# 清空 PYTHONPATH/PYTHONHOME），确认 GUI 不依赖宿主 Python 与 tkinter。
#
# 无 FUSE 环境下用 --appimage-extract-and-run 解包执行。
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 默认取 dist/ 下的第一个 AppImage，避免把绝对路径写死（CI 里工作目录不同）
if [ $# -ge 1 ]; then
  APPIMAGE="$1"
else
  APPIMAGE="$(find "$PROJECT_ROOT/dist" -maxdepth 1 -name '*.AppImage' 2>/dev/null | head -1)"
  [ -n "$APPIMAGE" ] || { echo "dist/ 下未找到 AppImage，请先构建或用参数指定路径"; exit 1; }
fi
APPIMAGE="$(readlink -f "$APPIMAGE")"

echo "=== 验证 AppImage: $(basename "$APPIMAGE") ==="

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

export DISPLAY=:99
export XDG_SESSION_TYPE=x11
export HOME="$WORK/home"
mkdir -p "$HOME"

# 启动 Xvfb
if ! xdpyinfo -display :99 >/dev/null 2>&1; then
  Xvfb :99 -screen 0 1280x800x24 >/tmp/xvfb-verify.log 2>&1 &
  sleep 2
fi

# ---------------------------------------------------------------- 测试 1
echo
echo "--- 测试 1: 解包内容完整性 ---"
cd "$WORK"
"$APPIMAGE" --appimage-extract >/dev/null 2>&1 || { echo "解包失败"; exit 1; }
SQ="$WORK/squashfs-root"
for f in AppRun usr/bin/python3.wrapper usr/bin/python3.real \
         usr/share/xenia-canary-configtool/app.py \
         usr/share/xenia-canary-configtool/data/schema.json \
         usr/share/applications/xenia-canary-configtool.desktop \
         xenia-canary-configtool.png .DirIcon; do
  if [ -e "$SQ/$f" ]; then echo "  ✓ $f"; else echo "  ✗ 缺失: $f"; fi
done

# ---------------------------------------------------------------- 测试 2
echo
echo "--- 测试 2: 捆绑解释器可独立启动（不依赖宿主 tkinter）---"
env -i HOME="$HOME" PATH=/usr/bin:/bin \
  "$SQ/usr/bin/python3.wrapper" -c "
import sys, os
print('  解释器:', sys.executable)
print('  PYTHONHOME:', os.environ.get('PYTHONHOME'))
import tkinter
print('  tkinter: OK, Tk 版本', tkinter.TkVersion)
print('  Tcl 库路径:', os.environ.get('TCL_LIBRARY'))
print('  Tk  库路径:', os.environ.get('TK_LIBRARY'))
" 2>&1 | sed 's/^/  /'

# ---------------------------------------------------------------- 测试 3
echo
echo "--- 测试 3: 用 AppRun 启动 GUI（隔离环境）---"
cat > "$HOME/xenia-canary.config.toml" <<'TOML'
[Display]
fullscreen = false
postprocess_antialiasing = ""
[GPU]
gpu = "vulkan"
draw_resolution_scale_x = 1
vsync = false
[General]
time_scalar = 1
[Logging]
log_level = 2
TOML
mkdir -p "$HOME/.config"
cp "$HOME/xenia-canary.config.toml" "$HOME/.config/xenia-canary.config.toml"

env -i HOME="$HOME" PATH=/usr/bin:/bin DISPLAY=:99 XDG_SESSION_TYPE=x11 \
  XENIA_CONFIGTOOL_DEBUG=1 "$SQ/AppRun" >"$WORK/apprun.log" 2>&1 &
APP_PID=$!
sleep 10

if kill -0 $APP_PID 2>/dev/null; then
  echo "  ✓ GUI 进程存活 (pid=$APP_PID)"
  mkdir -p "$PROJECT_ROOT/build"
  import -display :99 -window root "$WORK/verify.png" 2>/dev/null && \
    cp "$WORK/verify.png" "$PROJECT_ROOT/build/verify-appimage.png" && \
    echo "  ✓ 截图已保存: build/verify-appimage.png"
  kill $APP_PID 2>/dev/null
else
  echo "  ✗ GUI 进程已退出"
fi

echo
echo "--- AppRun 日志 ---"
sed 's/^/  /' "$WORK/apprun.log"

echo
echo "=== 验证结束 ==="
