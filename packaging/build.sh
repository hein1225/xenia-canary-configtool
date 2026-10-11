#!/usr/bin/env bash
# 构建 xenia-canary-configtool 的 AppImage。
#
# 步骤：
#   1. 组装 AppDir 目录结构
#   2. 复制应用源码、数据、图标与桌面元数据
#   3. 捆绑 Python 运行时与 Tk（SteamOS 为只读系统，必须自带）
#   4. 用 appimagetool 打包
#
# 用法：packaging/build.sh [输出目录]
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_ROOT/build/appimage"
APPDIR="$BUILD_DIR/XeniaCanaryConfigTool.AppDir"
OUT_DIR="${1:-$PROJECT_ROOT/dist}"
APP_ID="xenia-canary-configtool"
VERSION="1.0.0"
ARCH="x86_64"

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[!]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# ---------------------------------------------------------------- 前置检查

command -v python3 >/dev/null || die "缺少 python3"

APPIMAGETOOL="$PROJECT_ROOT/tools/appimagetool"
RUNTIME="$PROJECT_ROOT/runtime/runtime-x86_64"
[ -f "$APPIMAGETOOL" ] || die "缺少 appimagetool: $APPIMAGETOOL"
chmod +x "$APPIMAGETOOL" 2>/dev/null || true
[ -f "$RUNTIME" ] || die "缺少 AppImage runtime: $RUNTIME"

# ---------------------------------------------------------------- 1. 准备 AppDir

say "清理并创建 AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/lib" \
         "$APPDIR/usr/share/$APP_ID" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor" \
         "$APPDIR/usr/share/metainfo"

# ---------------------------------------------------------------- 2. 应用文件

say "复制应用源码"
cp "$PROJECT_ROOT/src/"*.py "$APPDIR/usr/share/$APP_ID/"
mkdir -p "$APPDIR/usr/share/$APP_ID/data"
cp "$PROJECT_ROOT/src/data/"*.json "$APPDIR/usr/share/$APP_ID/data/"

# 附带参考配置，便于用户对照与首次使用
if [ -f "$PROJECT_ROOT/reference.config.toml" ]; then
    cp "$PROJECT_ROOT/reference.config.toml" "$APPDIR/usr/share/$APP_ID/"
fi

say "复制桌面集成文件"
cp "$PROJECT_ROOT/packaging/$APP_ID.desktop" \
   "$APPDIR/usr/share/applications/$APP_ID.desktop"
# AppStream 要求 metainfo 的文件名与 XML 里的 <id> 完全一致，否则
# appimagetool 调 appstreamcli 校验时会报 metainfo-filename-cid-mismatch
# 并直接拒绝打包。这里从 XML 读取 <id> 作为目标文件名，避免两者脱钩。
APPSTREAM_ID="$(sed -n 's:.*<id>[[:space:]]*\([^<[:space:]]*\)[[:space:]]*</id>.*:\1:p' \
    "$PROJECT_ROOT/packaging/$APP_ID.appdata.xml" | head -1)"
[ -n "$APPSTREAM_ID" ] || die "无法从 appdata.xml 解析出 <id>（AppStream 必需）"
cp "$PROJECT_ROOT/packaging/$APP_ID.appdata.xml" \
   "$APPDIR/usr/share/metainfo/$APPSTREAM_ID.appdata.xml"
say "  AppStream id: $APPSTREAM_ID"

say "复制图标"
for size in 16 24 32 48 64 128 256 512; do
    src="$PROJECT_ROOT/assets/icons/$APP_ID-$size.png"
    [ -f "$src" ] || continue
    dst_dir="$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps"
    mkdir -p "$dst_dir"
    cp "$src" "$dst_dir/$APP_ID.png"
done
# AppImage 根目录图标
cp "$PROJECT_ROOT/assets/icons/$APP_ID-256.png" "$APPDIR/$APP_ID.png"
cp "$PROJECT_ROOT/assets/icons/$APP_ID-256.png" "$APPDIR/.DirIcon"
cp "$PROJECT_ROOT/packaging/$APP_ID.desktop" "$APPDIR/$APP_ID.desktop"

# ---------------------------------------------------------------- 3. 捆绑运行时

say "捆绑 Python 运行时（使 AppImage 在 SteamOS 等只读系统上独立可用）"

bundle_python() {
    local host_py
    host_py="$(command -v python3)"
    local py_ver
    py_ver="$("$host_py" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    say "宿主解释器: $host_py (Python $py_ver)"

    # --- 3a. 解释器本体与标准库
    mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/lib/python$py_ver"

    local prefix
    prefix="$("$host_py" -c 'import sys; print(sys.base_prefix)')"
    say "Python 前缀: $prefix"

    # 定位真实的解释器可执行文件
    local real_bin="$prefix/bin/python$py_ver"
    [ -x "$real_bin" ] || real_bin="$prefix/bin/python3"

    cp -L "$real_bin" "$APPDIR/usr/bin/python3"
    chmod +x "$APPDIR/usr/bin/python3"

    # 标准库（排除测试与无用的重型模块以控制体积）
    say "复制标准库…"
    for item in "$prefix"/lib/python"$py_ver"/*; do
        [ -e "$item" ] || continue
        local base
        base="$(basename "$item")"
        case "$base" in
            test|tests|idlelib|tkinter/test*|lib2to3|distutils|ensurepip|venv|__pycache__) continue ;;
            # config-<ver>-<triplet>/ 是 CPython 的开发用目录，只在装了
            # python3-dev 的机器上存在，里面有 libpython3.x.a（静态库）、
            # libpython3.x-pic.a 与 libpython3.x.so，合计约 35MB，运行期
            # 完全用不到。若不排除，同一份源码在装了 dev 包的环境（如 CI）
            # 会打出明显更大的包。
            config-*) continue ;;
            # 编译期头文件同理
            include) continue ;;
        esac
        cp -rL "$item" "$APPDIR/usr/lib/python$py_ver/" 2>/dev/null || true
    done

    # --- 3b. Tk 运行时（Tcl/Tk 库文件）
    say "复制 Tcl/Tk 运行时…"
    local tk_libdirs=()
    for d in "$prefix"/lib/tcl* "$prefix"/lib/tk* /usr/lib/tcl* /usr/lib/tk* \
             /usr/share/tcltk/tcl* /usr/share/tcltk/tk*; do
        [ -d "$d" ] && tk_libdirs+=("$d")
    done

    if [ ${#tk_libdirs[@]} -eq 0 ]; then
        warn "未找到 Tcl/Tk 库目录，GUI 可能依赖宿主系统"
    else
        for d in "${tk_libdirs[@]}"; do
            cp -rL "$d" "$APPDIR/usr/lib/" 2>/dev/null || true
        done
    fi

    # tkinter 的 C 扩展
    local tkinter_ext
    tkinter_ext="$(find "$prefix/lib/python$py_ver" -name '_tkinter*.so' 2>/dev/null | head -1 || true)"
    if [ -n "$tkinter_ext" ]; then
        cp -L "$tkinter_ext" "$APPDIR/usr/lib/python$py_ver/" 2>/dev/null || true
        say "已捆绑 _tkinter 扩展"
    else
        warn "未找到 _tkinter 扩展，GUI 将无法启动"
    fi

    # --- 3b-2. 字体（关键！Tk 在完全没有字体的环境下会直接抛
    #     "failed to allocate font due to internal system font engine problem"
    #     并崩溃。SteamOS 等精简系统字体不全，必须自带。）
    say "复制字体…"
    mkdir -p "$APPDIR/usr/share/fonts/truetype"
    local font_dirs=(/usr/share/fonts/truetype/dejavu /usr/share/fonts/truetype/wqy
                     /usr/share/fonts/truetype/liberation /usr/share/fonts/truetype/noto)
    local font_copied=0
    # 拉丁 + 几何符号（导航图标依赖 DejaVu 的几何符号覆盖）
    for f in DejaVuSans.ttf DejaVuSans-Bold.ttf DejaVuSansMono.ttf DejaVuSansMono-Bold.ttf; do
        local src="/usr/share/fonts/truetype/dejavu/$f"
        [ -f "$src" ] && { cp -L "$src" "$APPDIR/usr/share/fonts/truetype/"; font_copied=$((font_copied+1)); }
    done
    # 中文（文泉驿微米黑体积小、覆盖全，优先；退回文泉驿正黑/思源）
    for f in /usr/share/fonts/truetype/wqy/wqy-microhei.ttc \
             /usr/share/fonts/truetype/wqy/wqy-zenhei.ttc \
             /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc; do
        [ -f "$f" ] && { cp -L "$f" "$APPDIR/usr/share/fonts/truetype/"; font_copied=$((font_copied+1)); break; }
    done
    if [ "$font_copied" -eq 0 ]; then
        warn "未找到可捆绑的字体，界面在中文字体缺失的机器上可能显示异常"
    else
        say "已捆绑 $font_copied 个字体文件"
    fi

    # --- 3c. 关键共享库（Tk 依赖 X11 与字体栈）
    say "复制共享库依赖…"
    local libs=(
        libtk8.6.so libtcl8.6.so
        libX11.so.6 libXext.so.6 libXft.so.2 libXrender.so.1 libXss.so.1
        libfontconfig.so.1 libfreetype.so.6 libexpat.so.1
        libz.so.1 libbz2.so.1.0 liblzma.so.5 libffi.so.8
        libssl.so.3 libcrypto.so.3
        libreadline.so.8 libncursesw.so.6 libtinfo.so.6
        libgdbm.so.6 libgdbm_compat.so.4 libuuid.so.1
        libsqlite3.so.0 libpanelw.so.6
    )
    local copied=0
    for lib in "${libs[@]}"; do
        local found
        found="$(find /usr/lib /lib "$prefix/lib" -maxdepth 4 -name "$lib" 2>/dev/null | head -1 || true)"
        if [ -n "$found" ]; then
            cp -L "$found" "$APPDIR/usr/lib/" 2>/dev/null && copied=$((copied+1))
        fi
    done
    say "已复制 $copied 个共享库"
    return 0
}

bundle_python

# 生成解释器包装脚本：设定 PYTHONHOME，使捆绑的 lib 生效
PY_VER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

cat > "$APPDIR/usr/bin/python3.wrapper" <<'WRAP'
#!/bin/bash
# 捆绑 Python 的启动包装：确保使用 AppDir 内的标准库与 Tk 资源
HERE="$(dirname "$(readlink -f "${0}")")"
APPDIR="$(dirname "$(dirname "$HERE")")"
export PYTHONHOME="$APPDIR/usr"
export LD_LIBRARY_PATH="$APPDIR/usr/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"

# Tcl/Tk 需要知道自己的库目录位置
for d in "$APPDIR"/usr/lib/tcl8*; do
    [ -d "$d" ] && export TCL_LIBRARY="$d" && break
done
for d in "$APPDIR"/usr/lib/tk8*; do
    [ -d "$d" ] && export TK_LIBRARY="$d" && break
done

exec "$APPDIR/usr/bin/python3.real" "$@"
WRAP
chmod +x "$APPDIR/usr/bin/python3.wrapper"

# 真实解释器改名，包装脚本接管 python3
if [ -f "$APPDIR/usr/bin/python3" ] && [ ! -f "$APPDIR/usr/bin/python3.real" ]; then
    mv "$APPDIR/usr/bin/python3" "$APPDIR/usr/bin/python3.real"
fi

# ---------------------------------------------------------------- 4. AppRun

say "安装 AppRun"
cp "$PROJECT_ROOT/packaging/AppRun" "$APPDIR/AppRun"
chmod +x "$APPDIR/AppRun"

# ---------------------------------------------------------------- 5. 打包

say "打包 AppImage"
mkdir -p "$OUT_DIR"
OUT_FILE="$OUT_DIR/XeniaCanaryConfigTool-${VERSION}-${ARCH}.AppImage"

cd "$BUILD_DIR"
export ARCH
export VERSION

# 容器/无 FUSE 环境下用 --appimage-extract-and-run
if [ -e /dev/fuse ]; then
    "$APPIMAGETOOL" --runtime-file "$RUNTIME" "$APPDIR" "$OUT_FILE" 2>&1 | tail -20
else
    warn "未检测到 FUSE，使用 extract-and-run 模式打包"
    "$APPIMAGETOOL" --appimage-extract-and-run --runtime-file "$RUNTIME" \
        "$APPDIR" "$OUT_FILE" 2>&1 | tail -20
fi

[ -f "$OUT_FILE" ] || die "打包失败：未生成 $OUT_FILE"
chmod +x "$OUT_FILE"

say "完成：$OUT_FILE ($(du -h "$OUT_FILE" | cut -f1))"
