#!/usr/bin/env python3
"""分类导航的呈现元数据：图标、简介、排序权重、常用度。

关于图标对齐
------------
Unicode 符号的字形宽度因字体而异，直接混排会导致导航栏参差不齐。
本模块的做法是：
  1. 只选用「半角正方形」类符号（几何图形块），避免 emoji 与手写体符号
  2. 渲染时用等宽字体（见 theme.pick_mono_font），使每个图标占据完全相同的宽度
  3. 图标与文字之间用固定数量的空格分隔，保证名称左边界对齐

经实测，DejaVu Sans Mono 下下列符号宽度一致，可安全混用。
"""

from __future__ import annotations

# 分组图标：统一采用几何符号，风格一致、无 emoji 渲染差异
SECTION_ICONS: dict[str, str] = {
    "APU": "♫",         # 音频：双音符
    "CPU": "◎",         # 处理器：同心圆
    "Config": "⌘",      # 元数据：命令行符
    "Content": "❋",     # 内容授权：六角雪花
    "D3D12": "◇",       # Direct3D 12：空心菱形
    "Display": "◱",     # 显示输出：象限方框
    "GPU": "▤",         # 图形：横线方框
    "GPU.Debug": "⊘",   # 图形调试：禁用符
    "General": "✳",     # 常规：六角星
    "HID": "⊙",         # 输入设备：圆中圆
    "HID.Key": "⌸",     # 键盘：键位符
    "Kernel": "◈",      # 内核：菱形套菱形
    "Logging": "≡",     # 日志：三横线
    "Memory": "▦",      # 内存：网格
    "Profiles": "☺",    # 玩家档案：笑脸
    "SDL": "⊞",         # SDL：方格加号
    "Storage": "▥",     # 存储：竖线方框
    "UI": "⍟",          # 界面：圈中星
    "Video": "▷",       # 视频：空心三角
    "Vulkan": "△",      # Vulkan：空心上三角
    "Win32": "⊟",       # Windows 专属：方格减号
    "x64": "✚",         # x64 后端：粗十字
    "XConfig": "⊕",     # 账号区域：圆中加号
}

# 大类导航图标
NAV_ICONS: dict[str, str] = {
    "common": "✳",
    "graphics": "◈",
    "system": "◉",
    "developer": "⊘",
}

# 图标列宽：以「等宽字体下的字符数」计，保证左边界对齐
ICON_PAD = 2


def format_icon_label(icon: str, text: str) -> str:
    """把图标与文字组合成对齐的标签。

    图标用等宽字体渲染（调用方负责），加上固定空格作为分隔，
    使所有行的文字起始位置一致。
    """
    return f"{icon}{' ' * ICON_PAD}{text}"


# 分组一句话简介（中文 / 英文）
SECTION_BLURB: dict[str, dict[str, str]] = {
    "Display": {"zh": "画面输出、全屏、抗锯齿与放大方式", "en": "Image output, fullscreen, AA and upscaling"},
    "GPU": {"zh": "渲染分辨率、纹理缓存、画质与兼容性", "en": "Resolution scale, texture cache, accuracy"},
    "Video": {"zh": "视频制式、内部渲染分辨率、3D 模式", "en": "Video mode, internal resolution, 3D mode"},
    "APU": {"zh": "音频后端与 XMA 解码", "en": "Audio backend and XMA decoding"},
    "HID": {"zh": "手柄、键盘与震动设置", "en": "Controllers, keyboard and vibration"},
    "HID.Key": {"zh": "键盘按键到 Xbox 手柄的映射", "en": "Keyboard-to-gamepad key bindings"},
    "General": {"zh": "启动行为、补丁与最近的游戏", "en": "Launch behavior, patches, recent titles"},
    "Storage": {"zh": "存档、缓存与内容目录位置", "en": "Saves, cache and content folders"},
    "UI": {"zh": "窗口尺寸、字体与界面提示", "en": "Window size, fonts and on-screen UI"},
    "Profiles": {"zh": "开机自动载入的玩家档案", "en": "Profiles loaded on boot"},
    "Content": {"zh": "内容授权掩码", "en": "Content license mask"},
    "Kernel": {"zh": "主机类型、系统版本与更新", "en": "Console type, system version, updates"},
    "Logging": {"zh": "日志级别与输出目标", "en": "Log level and output targets"},
    "SDL": {"zh": "手柄映射数据库文件", "en": "Controller mapping database file"},
    "Win32": {"zh": "Windows 专属计时器与调度（Linux 下无效）", "en": "Windows-only timers and scheduling"},
    "D3D12": {"zh": "Direct3D 12 后端专属细调（选它需把 gpu 设为 d3d12）", "en": "Direct3D 12-only fine-tuning (set gpu to d3d12)"},
    "Vulkan": {"zh": "Vulkan 后端专属细调（选它需把 gpu 设为 vulkan）", "en": "Vulkan-only fine-tuning (set gpu to vulkan)"},
    "CPU": {"zh": "CPU 模拟后端与调试断点", "en": "CPU backend and debug breakpoints"},
    "GPU.Debug": {"zh": "图形管线底层调试开关", "en": "Low-level graphics pipeline debugging"},
    "Memory": {"zh": "内存分配与保护策略", "en": "Memory allocation and protection"},
    "x64": {"zh": "x64 重编译后端与指令集", "en": "x64 recompiler backend and ISA"},
    "Config": {"zh": "配置文件内部版本标记", "en": "Internal config version marker"},
    "XConfig": {"zh": "上报给主机的账号国家与语言", "en": "Account country and language reported to the console"},
}

# 导航分组：把 22 个 section 归入 4 个大类
NAV_GROUPS: list[dict] = [
    {
        "id": "common",
        "icon": "✳",
        "name": {"zh": "常用设置", "en": "Essentials"},
        "desc": {
            "zh": "影响游戏体验的主要选项，日常调优先看这里",
            "en": "The options that affect gameplay most — start here",
        },
        "sections": ["Display", "GPU", "Video", "APU", "HID", "HID.Key", "General", "Storage"],
    },
    {
        "id": "graphics",
        "icon": "◈",
        "name": {"zh": "图形后端", "en": "Graphics backends"},
        "desc": {
            "zh": "d3d12 与 vulkan 二选一，由「常用设置 → GPU」的 gpu 项决定；这里是各后端的专属细调",
            "en": "Pick one via the 'gpu' option under Essentials → GPU; these are per-backend fine-tuning",
        },
        "sections": ["D3D12", "Vulkan"],
    },
    {
        "id": "system",
        "icon": "◉",
        "name": {"zh": "系统与存储", "en": "System & storage"},
        "desc": {
            "zh": "主机模拟、存档路径与界面外观",
            "en": "Console emulation, save paths and interface",
        },
        "sections": ["Kernel", "Profiles", "Content", "UI", "SDL", "Logging", "XConfig"],
    },
    {
        "id": "developer",
        "icon": "⊘",
        "name": {"zh": "开发者选项", "en": "Developer options"},
        "desc": {
            "zh": "调试与诊断用途，普通游玩无需改动，改错可能导致游戏异常",
            "en": "For debugging and diagnostics — wrong values can break games",
        },
        "sections": ["CPU", "GPU.Debug", "Memory", "x64", "Config", "Win32"],
    },
]

# 后端专属分组：只有把 gpu 选成对应值时才生效，避免用户误以为是并列的两个后端
BACKEND_SECTIONS: dict[str, str] = {
    "D3D12": "d3d12",
    "Vulkan": "vulkan",
}

# 决定图形后端的开关项
BACKEND_CHOICE_KEY = "gpu"

# 「自动」取值：选中它时各分支都可能生效，故全部显示
AUTO_VALUES: set[str] = {"any"}

# ---------------------------------------------------------------- 依从规则
# 有些设置项只在另一个开关取特定值时才生效（甚至只在该后端下才存在）。
# 规则结构：{"label_key": 取值, "when": [(开关项, {允许的取值}), ...]}
# 界面据此隐藏不生效的项；开关为「自动」时全部保留，因为它可能落到任一边。
DEPENDENT_KEYS: list[dict] = [
    {
        "label": {"zh": "D3D12 专用", "en": "D3D12 only"},
        "pattern": "render_target_path_d3d12",
        "when": [("gpu", {"d3d12", "any"})],
        # 这两项在 toml 里属于 [GPU] 段，但对用户来说它们是「各后端的专属项」。
        # 若只按 toml 分组摆，用户去「图形后端 → Vulkan」里永远找不到它们，
        # 因此额外挂到对应后端分组下（原分组仍然保留，搜索与直接定位都不受影响）。
        "also_in": "D3D12",
    },
    {
        "label": {"zh": "Vulkan 专用", "en": "Vulkan only"},
        "pattern": "render_target_path_vulkan",
        "when": [("gpu", {"vulkan", "any"})],
        "also_in": "Vulkan",
    },
]


def also_in_section(key: str) -> str | None:
    """返回该设置项额外归属的后端分组（无则为 None）。"""
    for rule in DEPENDENT_KEYS:
        if rule["pattern"] == key:
            return rule.get("also_in")
    return None


def section_matches(section: str, key: str) -> bool:
    """判断某设置项是否应出现在指定分组的列表中。

    除了 toml 原始分组，还包含 DEPENDENT_KEYS 声明的「额外归属」，
    让后端专属项在对应后端分组里也能被看到。
    """
    return also_in_section(key) == section

# 分组级依从：整组只对某个后端有意义
GROUP_WHEN: dict[str, list[tuple[str, set[str]]]] = {
    "D3D12": [("gpu", {"d3d12", "any"})],
    "Vulkan": [("gpu", {"vulkan", "any"})],
}


def _current(values: dict, key: str) -> str:
    return str(values.get(key, "")).strip().strip('"').lower()


def rule_active(values: dict, rule: dict) -> bool:
    """判断一条依从规则在当前配置下是否成立。"""
    for key, allowed in rule["when"]:
        cur = _current(values, key)
        if cur in AUTO_VALUES:      # 自动：可能落到任一分支，视为生效
            continue
        if cur not in allowed:
            return False
    return True


def group_visible(values: dict, section: str) -> bool:
    """分组在当前配置下是否应当显示。"""
    for key, allowed in GROUP_WHEN.get(section, []):
        cur = _current(values, key)
        if cur in AUTO_VALUES:
            continue
        if cur not in allowed:
            return False
    return True


def key_visible(values: dict, key: str) -> bool:
    """单个设置项在当前配置下是否应当显示。"""
    for rule in DEPENDENT_KEYS:
        if rule["pattern"] == key:
            return rule_active(values, rule)
    return True


def affects_visibility(key: str) -> bool:
    """改动该项是否会影响其它分组/设置项的可见性。"""
    for key2, _allowed in GROUP_WHEN.get("D3D12", []):
        if key == key2:
            return True
    for rule in DEPENDENT_KEYS:
        for key2, _allowed in rule["when"]:
            if key == key2:
                return True
    return False


def backend_mode(values: dict) -> str:
    """返回后端模式：d3d12 / vulkan / any / null。"""
    return _current(values, BACKEND_CHOICE_KEY) or "any"


def hidden_reason(values: dict, section: str) -> str | None:
    """分组被隐藏时，说明它需要什么取值才出现。"""
    for key, allowed in GROUP_WHEN.get(section, []):
        cur = _current(values, key)
        if cur in AUTO_VALUES:
            continue
        if cur not in allowed:
            want = "/".join(sorted(allowed - AUTO_VALUES))
            return f"{key} = {want}"
    return None

# 后端选项的中文名（用于界面把 d3d12/vulkan 显示得更明确）
BACKEND_LABELS: dict[str, dict[str, str]] = {
    "d3d12": {"zh": "Direct3D 12", "en": "Direct3D 12"},
    "vulkan": {"zh": "Vulkan", "en": "Vulkan"},
    "any": {"zh": "自动选择", "en": "Automatic"},
    "null": {"zh": "不使用图形", "en": "No graphics"},
}

# 掌机/SteamOS 用户最常调整的项目：置顶推荐
FEATURED_KEYS: list[str] = [
    "draw_resolution_scale_x",
    "draw_resolution_scale_y",
    "gpu",
    "fullscreen",
    "vsync",
    "framerate_limit",
    "postprocess_scaling_and_sharpening",
    "postprocess_antialiasing",
    "async_shader_compilation",
    "texture_cache_memory_limit_soft",
    "storage_root",
    "hid",
    "time_scalar",
]

# 推荐值预设（针对掌机常见场景）——展示用，需用户确认后写入
DEVICE_PRESETS: list[dict] = [
    {
        "id": "steamdeck",
        "name": {"zh": "Steam Deck / 掌机（720p 省电）", "en": "Steam Deck / handheld (720p, power save)"},
        "values": {
            "gpu": "vulkan",
            "draw_resolution_scale_x": 1,
            "draw_resolution_scale_y": 1,
            "vsync": True,
            "framerate_limit": 30,
            "async_shader_compilation": True,
        },
    },
    {
        "id": "balanced",
        "name": {"zh": "均衡（2x 分辨率缩放）", "en": "Balanced (2x resolution scale)"},
        "values": {
            "gpu": "vulkan",
            "draw_resolution_scale_x": 2,
            "draw_resolution_scale_y": 2,
            "vsync": False,
            "framerate_limit": 60,
        },
    },
    {
        "id": "quality",
        "name": {"zh": "画质优先（3x + 锐化）", "en": "Quality first (3x + sharpening)"},
        "values": {
            "gpu": "vulkan",
            "draw_resolution_scale_x": 3,
            "draw_resolution_scale_y": 3,
            "postprocess_scaling_and_sharpening": "fsr",
            "vsync": False,
            "framerate_limit": 0,
        },
    },
]


def section_to_nav(section: str) -> str:
    """返回某分组所属的导航大类 id。"""
    for g in NAV_GROUPS:
        if section in g["sections"]:
            return g["id"]
    return "system"


def nav_icon(section: str) -> str:
    return SECTION_ICONS.get(section, "•")


def nav_blurb(lang: str, section: str) -> str:
    table = SECTION_BLURB.get(section)
    if not table:
        return ""
    return table.get(lang) or table.get("en") or ""
