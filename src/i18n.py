#!/usr/bin/env python3
"""界面文案与配置说明的双语资源。

说明文本的策略：
  * zh：使用人工/子智能体翻译的中文说明
  * en：直接沿用 xenia 官方 config.toml 的英文原文注释（最权威、不会失真）

界面框架文案（按钮、菜单、提示）在 UI_STRINGS 中集中定义。
"""
from __future__ import annotations

import json
from pathlib import Path

LANGUAGES = ("zh", "en")
LANGUAGE_NAMES = {"zh": "简体中文", "en": "English"}

# ---------------------------------------------------------------- 界面文案

UI_STRINGS: dict[str, dict[str, str]] = {
    "app_title": {"zh": "Xenia Canary 配置工具", "en": "Xenia Canary Config Tool"},
    "menu_file": {"zh": "文件", "en": "File"},
    "menu_open": {"zh": "打开配置文件…", "en": "Open Config File…"},
    "menu_reload": {"zh": "重新载入", "en": "Reload"},
    "menu_save": {"zh": "保存", "en": "Save"},
    "menu_save_as": {"zh": "另存为…", "en": "Save As…"},
    "menu_restore_defaults": {"zh": "恢复默认值", "en": "Restore Defaults"},
    "menu_exit": {"zh": "退出", "en": "Exit"},
    "menu_settings": {"zh": "设置", "en": "Settings"},
    "menu_language": {"zh": "语言 / Language", "en": "Language / 语言"},
    "menu_autobackup": {"zh": "保存前自动备份", "en": "Back up before saving"},
    "menu_show_advanced": {"zh": "显示开发者选项", "en": "Show developer options"},
    "menu_help": {"zh": "帮助", "en": "Help"},
    "menu_about": {"zh": "关于", "en": "About"},
    "menu_shortcuts": {"zh": "快捷键", "en": "Shortcuts"},
    "search_placeholder": {"zh": "搜索设置项（名称或说明）…", "en": "Search settings (name or description)…"},
    "col_key": {"zh": "设置项", "en": "Setting"},
    "col_brief": {"zh": "中文名", "en": "Name"},
    "col_value": {"zh": "当前值", "en": "Value"},
    "col_modified": {"zh": "已修改", "en": "Modified"},
    "detail_title": {"zh": "设置详情", "en": "Setting details"},
    "detail_desc": {"zh": "说明", "en": "Description"},
    "detail_default": {"zh": "默认值", "en": "Default"},
    "detail_type": {"zh": "类型", "en": "Type"},
    "detail_section": {"zh": "分组", "en": "Section"},
    "detail_revert": {"zh": "还原此项", "en": "Revert this setting"},
    "btn_refresh": {"zh": "刷新", "en": "Refresh"},
    "btn_search": {"zh": "搜索", "en": "Search"},
    "btn_clear": {"zh": "清空", "en": "Clear"},
    "btn_browse": {"zh": "浏览…", "en": "Browse…"},
    "btn_apply": {"zh": "应用", "en": "Apply"},
    "btn_close": {"zh": "关闭", "en": "Close"},
    "btn_ok": {"zh": "确定", "en": "OK"},
    "btn_cancel": {"zh": "取消", "en": "Cancel"},
    "btn_yes": {"zh": "是", "en": "Yes"},
    "btn_no": {"zh": "否", "en": "No"},
    "status_ready": {"zh": "就绪", "en": "Ready"},
    "status_loaded": {"zh": "已载入：{path}", "en": "Loaded: {path}"},
    "status_modified_count": {"zh": "已修改 {n} 项", "en": "{n} setting(s) modified"},
    "status_saved": {"zh": "已保存到 {path}", "en": "Saved to {path}"},
    "status_backup": {"zh": "备份：{path}", "en": "Backup: {path}"},
    "status_no_changes": {"zh": "没有需要保存的改动", "en": "No changes to save"},
    "status_search_result": {"zh": "找到 {n} 项", "en": "{n} result(s)"},
    "filter_all": {"zh": "全部分组", "en": "All sections"},
    "filter_modified_only": {"zh": "仅显示已修改", "en": "Modified only"},
    "dlg_open_title": {"zh": "选择 xenia-canary.config.toml", "en": "Select xenia-canary.config.toml"},
    "dlg_saveas_title": {"zh": "另存为", "en": "Save As"},
    "dlg_confirm_save": {"zh": "确定要写入配置文件吗？", "en": "Write changes to the config file?"},
    "dlg_confirm_save_body": {
        "zh": "将写入：\n{path}\n\n共 {n} 项改动。{backup_note}",
        "en": "Will write to:\n{path}\n\n{n} change(s). {backup_note}",
    },
    "dlg_backup_note_on": {"zh": "保存前会自动创建备份。", "en": "A backup will be created first."},
    "dlg_backup_note_off": {"zh": "未启用备份，原文件将被直接覆盖。", "en": "Backup is off; the original file will be overwritten."},
    "dlg_error_title": {"zh": "错误", "en": "Error"},
    "dlg_warn_title": {"zh": "提示", "en": "Notice"},
    "dlg_confirm_revert": {"zh": "确定要还原此项为默认值吗？", "en": "Revert this setting to its default?"},
    "dlg_confirm_restore_all": {
        "zh": "确定要把全部设置恢复为默认值吗？此操作不会立即写盘，你可以先检查再保存。",
        "en": "Reset all settings to defaults? Nothing is written to disk until you save.",
    },
    "err_load_failed": {"zh": "载入失败：{err}", "en": "Failed to load: {err}"},
    "err_save_failed": {"zh": "保存失败：{err}", "en": "Failed to save: {err}"},
    "err_invalid_value": {"zh": "无效的值：{err}", "en": "Invalid value: {err}"},
    "err_not_found": {"zh": "文件不存在", "en": "File not found"},
    "err_no_file": {"zh": "尚未载入配置文件", "en": "No config file loaded"},
    "about_body": {
        "zh": (
            "Xenia Canary 配置工具\n\n"
            "用于图形化编辑 xenia-canary.config.toml 的 Linux 桌面工具。\n"
            "覆盖全部 {total} 项设置，支持中英文界面实时切换。\n\n"
            "设置项位置：{path}\n"
            "版本：{version}"
        ),
        "en": (
            "Xenia Canary Config Tool\n\n"
            "A Linux desktop tool for editing xenia-canary.config.toml graphically.\n"
            "Covers all {total} settings with live Chinese/English switching.\n\n"
            "Config file: {path}\n"
            "Version: {version}"
        ),
    },
    "shortcuts_body": {
        "zh": (
            "Ctrl+O    打开配置文件\n"
            "Ctrl+S    保存\n"
            "Ctrl+Shift+S    另存为\n"
            "Ctrl+F    聚焦搜索框\n"
            "F5        重新载入\n"
            "Ctrl+Q    退出\n"
            "Esc       清空搜索 / 关闭对话框"
        ),
        "en": (
            "Ctrl+O    Open config file\n"
            "Ctrl+S    Save\n"
            "Ctrl+Shift+S    Save As\n"
            "Ctrl+F    Focus search box\n"
            "F5        Reload\n"
            "Ctrl+Q    Quit\n"
            "Esc       Clear search / close dialog"
        ),
    },
    "value_true": {"zh": "启用", "en": "Enabled"},
    "value_false": {"zh": "禁用", "en": "Disabled"},
    "value_true_short": {"zh": "开", "en": "On"},
    "value_false_short": {"zh": "关", "en": "Off"},
    "modified_mark": {"zh": "●", "en": "●"},
    "hint_string_empty": {"zh": "（空）", "en": "(empty)"},
    "btn_add_key": {"zh": "新增设置项…", "en": "Add setting…"},
    "btn_remove_key": {"zh": "删除此项", "en": "Remove this setting"},
    "dlg_add_key_title": {"zh": "新增设置项", "en": "Add setting"},
    "err_key_exists": {"zh": "该设置项已存在", "en": "This setting already exists"},
    "err_key_invalid": {"zh": "设置项名称无效（只允许字母、数字、下划线）", "en": "Invalid setting name (letters, digits, underscore only)"},
    "warn_unknown_key": {
        "zh": "这是配置文件中尚不存在的设置项，将由本工具添加。",
        "en": "This setting does not exist in the file yet; it will be added by this tool.",
    },
    # ---- 分类导航相关
    "nav_sections": {"zh": "分组（共 {n} 类）", "en": "Sections ({n} total)"},
    "nav_item_count": {"zh": "{n} 项", "en": "{n}"},
    "unit_sections": {"zh": "个分组", "en": "sections"},
    "nav_group_label": {"zh": "分类导航", "en": "Categories"},
    "list_all_sections": {"zh": "全部分组", "en": "All sections"},
    "btn_back_all": {"zh": "← 显示全部", "en": "← Show all"},
    "unit_items": {"zh": "项", "en": "items"},
    "backend_bar": {
        "zh": "{value} 专属设置（当前未启用）",
        "en": "{value}-only settings (not currently in use)",
    },
    "backend_bar_active": {
        "zh": "{value} 专属设置（当前正在使用）",
        "en": "{value}-only settings (currently in use)",
    },
    "backend_sub": {
        "zh": "这些项只对选中的图形后端生效；后端由 GPU 分组的 gpu 项决定。",
        "en": "These apply only to the selected graphics backend; it is chosen by the 'gpu' option in the GPU section.",
    },
    "backend_tip": {"zh": "仅当 gpu = {value} 时生效", "en": "Applies only when gpu = {value}"},
    "backend_go": {"zh": "去设置 gpu 项…", "en": "Set the gpu option…"},
    "backend_go_active": {"zh": "已启用该后端", "en": "Backend in use"},
    "hidden_head": {"zh": "以下分组当前不显示：{names}", "en": "Currently hidden: {names}"},
    "hidden_body": {
        "zh": "它们只在特定后端下生效 —— {detail}。把 gpu 改为 any（自动）可同时显示两边。",
        "en": "They apply only with a specific backend — {detail}. Set gpu to any to show both.",
    },
    "dep_hidden_n": {"zh": "（已隐藏 {n} 项不适用于当前后端的设置）",
                     "en": "({n} options not applicable to the current backend are hidden)"},
    "card_featured_n": {"zh": "{n} 项常用推荐", "en": "{n} recommended"},
    "card_all_advanced": {
        "zh": "本组的 {n} 项都属于高级选项，仅在「开发者选项」大类下显示。"
              "要在这里查看，请先勾选顶部的「显示高级选项」，或切换到「开发者选项」。",
        "en": "All {n} options here are advanced and only appear under "
              "\"Developer options\". Tick \"Show advanced options\" above, "
              "or switch to that category."},
    "list_all_advanced": {
        "zh": "「{n} 项」其实一项都没显示：本组全部属于高级选项，默认视图中被隐藏。",
        "en": "None shown: every option in this section is advanced and hidden "
              "in the default view."},
    "list_all_advanced_hint": {
        "zh": "这些项只影响模拟器底层行为，普通游戏无需调整。需要时可前往「开发者选项」查看。",
        "en": "They only affect low-level emulator behaviour and rarely need "
              "tuning. Open \"Developer options\" to see them."},
    "btn_go_developer": {"zh": "前往开发者选项", "en": "Open Developer options"},
    "menu_presets": {"zh": "掌机预设…", "en": "Handheld presets…"},
    "preset_no_change": {"zh": "当前配置已经符合该预设，无需改动。",
                         "en": "Your configuration already matches this preset."},
    "preset_confirm_head": {"zh": "将套用预设「{name}」，以下设置会被修改：",
                            "en": "Applying preset \"{name}\". These settings will change:"},
    "preset_more": {"zh": "另有 {n} 项…", "en": "and {n} more…"},
    "preset_confirm_tail": {"zh": "改动会标记为已修改，需再点「保存」才会写入文件。",
                            "en": "Changes are marked as pending — click Save to write them to the file."},
    "preset_applied": {"zh": "已套用预设，{n} 项待保存。", "en": "Preset applied: {n} change(s) pending."},
    "val_on": {"zh": "开", "en": "On"},
    "val_off": {"zh": "关", "en": "Off"},
    "dlg_info_title": {"zh": "提示", "en": "Information"},
    "card_modified_n": {"zh": "已改 {n} 项", "en": "{n} changed"},
    "status_showing": {"zh": "显示 {shown} / {total} 项设置", "en": "Showing {shown} of {total} settings"},
    "detail_hint": {
        "zh": "在列表中选中一项设置即可在此编辑。\n"
              "把鼠标停在某一行上会弹出该设置的完整说明（触摸屏请用「查看说明」按钮）。",
        "en": "Select a setting in the list to edit it here.\n"
              "Hover a row to see its full description (on touchscreens, use the "
              "\"Show description\" button).",
    },
    "btn_show_desc": {"zh": "查看说明", "en": "Show description"},
    "detail_modified": {"zh": "已修改", "en": "modified"},
    "label_choices": {"zh": "可选：", "en": "Choices:"},
    "ask_discard": {
        "zh": "放弃未保存的改动并重新载入？",
        "en": "Discard unsaved changes and reload?",
    },
    "ask_quit_unsaved": {
        "zh": "有未保存的改动，确定退出吗？",
        "en": "There are unsaved changes. Quit anyway?",
    },
    "menu_categories": {"zh": "分类", "en": "Categories"},
    "btn_apply_preset": {"zh": "应用此预设", "en": "Apply preset"},
    "empty_title": {"zh": "尚未载入配置文件", "en": "No config file loaded"},
    "empty_body": {
        "zh": "点击「打开配置文件…」选择你的 xenia-canary.config.toml。\n"
              "载入后即可按左侧分类浏览并修改全部设置，保存时会默认写回原文件。",
        "en": "Click \"Open Config File…\" and pick your xenia-canary.config.toml.\n"
              "Once loaded, you can browse and edit every setting by category on the "
              "left; saving writes back to the original file by default.",
    },
    "empty_hint_paths": {
        "zh": "工具会自动尝试以下常见位置：\n"
              "  ~/.config/xenia-canary.config.toml\n"
              "  ~/.local/share/xenia-canary/xenia-canary.config.toml\n"
              "  Steam 兼容层前缀（compatdata）内的 AppData\\Roaming 目录\n"
              "若 xenia 可执行文件旁存在 portable.txt，则优先使用同目录的配置。",
        "en": "The tool automatically probes these common locations:\n"
              "  ~/.config/xenia-canary.config.toml\n"
              "  ~/.local/share/xenia-canary/xenia-canary.config.toml\n"
              "  AppData\\Roaming inside a Steam compatibility prefix (compatdata)\n"
              "If portable.txt sits next to the xenia executable, its folder wins.",
    },
}

SECTION_NAMES: dict[str, dict[str, str]] = {
    "APU": {"zh": "音频（APU）", "en": "Audio (APU)"},
    "CPU": {"zh": "处理器（CPU）", "en": "Processor (CPU)"},
    "Config": {"zh": "配置元数据", "en": "Config metadata"},
    "Content": {"zh": "内容授权", "en": "Content licensing"},
    "D3D12": {"zh": "Direct3D 12", "en": "Direct3D 12"},
    "Display": {"zh": "显示输出", "en": "Display output"},
    "GPU": {"zh": "图形（GPU）", "en": "Graphics (GPU)"},
    "GPU.Debug": {"zh": "图形调试", "en": "Graphics debugging"},
    "General": {"zh": "常规", "en": "General"},
    "HID": {"zh": "输入设备", "en": "Input devices"},
    "HID.Key": {"zh": "键盘映射", "en": "Keyboard bindings"},
    "Kernel": {"zh": "内核模拟", "en": "Kernel emulation"},
    "Logging": {"zh": "日志", "en": "Logging"},
    "Memory": {"zh": "内存", "en": "Memory"},
    "Profiles": {"zh": "玩家档案", "en": "Profiles"},
    "SDL": {"zh": "SDL 控制器", "en": "SDL controller"},
    "Storage": {"zh": "存储路径", "en": "Storage paths"},
    "UI": {"zh": "界面", "en": "Interface"},
    "Video": {"zh": "视频输出", "en": "Video output"},
    "Vulkan": {"zh": "Vulkan", "en": "Vulkan"},
    "Win32": {"zh": "Windows 专属", "en": "Windows-specific"},
    "x64": {"zh": "x64 后端", "en": "x64 backend"},
    "XConfig": {"zh": "账号区域", "en": "Account region"},
}

# 开发者/调试向分组：默认折叠，可用「显示开发者选项」开关揭示
ADVANCED_SECTIONS = {"CPU", "GPU.Debug", "Logging", "Memory", "x64", "Kernel", "Config", "Win32"}

# xenia 官方源码中标记为调试用途的 key（即便不在高级分组内也归为开发者选项）
ADVANCED_KEYS = {
    "debug", "break_on_start", "break_on_instruction", "break_condition_gpr",
    "break_condition_op", "break_condition_truncate", "break_condition_value",
    "break_on_unimplemented_instructions", "d3d12_debug", "d3d12_break_on_error",
    "d3d12_break_on_warning", "vulkan_validation", "imgui_debug", "show_profiler",
    "profiler_dpi_scaling", "debug_symbol_loader", "trace_gpu_stream",
    "trace_function_coverage", "trace_function_data", "trace_function_references",
    "trace_functions", "disassemble_functions", "store_all_context_values",
    "validate_hir", "dump_shaders", "dxbc_source_map", "disassemble_pm4",
    "enable_console", "log_to_debugprint", "kernel_pix", "staging_mode",
    "kernel_cert_monitor", "kernel_debug_monitor", "disassemble_functions",
}


class Resources:
    """加载并缓存双语资源。"""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.schema: dict = {}
        self.desc_zh: dict[str, str] = {}
        self.desc_en: dict[str, str] = {}
        self.names_zh: dict[str, str] = {}
        self.xconfig: dict[str, list[dict]] = {}
        self.defaults: dict[str, object] = {}
        self._load()

    def _load(self) -> None:
        schema_path = self.data_dir / "schema.json"
        if schema_path.exists():
            self.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        else:
            self.schema = {"entries": [], "sections": {}, "total": 0}

        for e in self.schema.get("entries", []):
            self.desc_en[e["key"]] = e.get("comment", "")

        zh_path = self.data_dir / "desc_zh.json"
        if zh_path.exists():
            self.desc_zh = json.loads(zh_path.read_text(encoding="utf-8"))

        # 中文名（列表「说明」列用）。英文版不显示这一列，故无需英文版。
        names_path = self.data_dir / "names_zh.json"
        if names_path.exists():
            self.names_zh = json.loads(names_path.read_text(encoding="utf-8"))

        # [XConfig] 的取值对照表（国家 / 语言）。
        # 这两项本身是自由整数，配置文件只写了 ISO 二字码，
        # 界面据此渲染成「中国 / China」这样的可读下拉框。
        xc_path = self.data_dir / "xconfig_choices.json"
        if xc_path.exists():
            self.xconfig = json.loads(xc_path.read_text(encoding="utf-8"))

    def lookup(self, key: str, raw: str, lang: str) -> str:
        """把 [XConfig] 的整数值翻成可读名称。

        找不到对应项时原样返回，绝不臆造。
        """
        table = self.xconfig.get(key)
        if not table:
            return raw
        try:
            num = int(str(raw).strip())
        except (TypeError, ValueError):
            return raw
        for item in table:
            if item["value"] == num:
                return item.get(lang) or item.get("zh") or raw
        return raw

    def choice_labels(self, key: str, lang: str) -> tuple[list[str], list[str]]:
        """给出下拉框用的显示标签与对应的实际取值。

        返回 (labels, values)，两者等长且一一对应：
        标签形如 `中国 (20)`，取值形如 `20`。
        """
        table = self.xconfig.get(key) or []
        labels, values = [], []
        for item in table:
            name = item.get(lang) or item.get("zh") or item.get("code", "")
            labels.append(f"{name} ({item['value']})")
            values.append(str(item["value"]))
        return labels, values

    def t(self, lang: str, key: str, **kwargs) -> str:
        """取界面文案。"""
        table = UI_STRINGS.get(key)
        if not table:
            return key
        text = table.get(lang) or table.get("en") or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text

    def section_name(self, lang: str, section: str) -> str:
        table = SECTION_NAMES.get(section)
        if table:
            return table.get(lang) or table.get("en") or section
        return section

    def describe(self, lang: str, key: str) -> str:
        """取某个设置项的说明文本。zh 缺失时回落英文原文。"""
        if lang == "zh":
            return self.desc_zh.get(key) or self.desc_en.get(key, "")
        return self.desc_en.get(key, "")

    def brief(self, lang: str, key: str) -> str:
        """取设置项的简短中文名，用于列表内联显示。

        仅中文版有值；英文版返回空串（调用方据此隐藏该列）。
        """
        if lang != "zh":
            return ""
        return self.names_zh.get(key, "")
