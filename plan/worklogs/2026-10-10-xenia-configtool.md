# Xenia Canary 配置工具 — 工作日志

## 需求

把 xenia-canary 的 265 项设置做成 Linux 图形界面，交付单文件 AppImage。

原始要求：
1. 可选择 `xenia-canary.config.toml` 位置，修改时默认覆盖原位置
2. 同步 TOML 中全部设置与说明
3. 支持中文与英文两个语言版本
4. 英文翻译由 1 个 hy3 子智能体完成，我负责校对

追加要求：
5. 支持 Wayland，主要用于 SteamOS 等掌机
6. 界面按 TOML 分组做好分类，采用分类导航展示
7. 子智能体使用 Hy3 模型
8. 第二子智能体用 workbuddy-global 的 hy4 模型做翻译校对
9. 每个设置说明用鼠标悬停显示，节省空间
10. 主题色采用海蓝色
11. 所有地方的图标大小整齐

## 交付物

| 文件 | 说明 |
|---|---|
| `dist/XeniaCanaryConfigTool-1.0.0-x86_64.AppImage` | 单文件交付，16MB |
| `README.md` | 使用说明 |
| `src/` | 源码 |
| `packaging/` | 构建脚本与桌面集成文件 |

## 技术决策

### 为什么用 Python + Tkinter
- 用户选定该技术栈
- Tk 8.6 在 SteamOS 上随系统可用（但为保险仍捆绑运行时）
- 无需编译，源码可直接审阅

### 格式保全：行级编辑而非整体重写
直接读写 TOML 会丢失注释与排版。采用 `TomlDoc` 做行级编辑：
- 解析每行为 `{section, key, value, comment}` 结构
- 修改时只替换目标行，其余原样保留
- 验证：读入再序列化可**逐字节一致**；改 3 项只有 3 行变化

### 运行时捆绑
SteamOS 根文件系统只读，无法 `pip install`。构建脚本把宿主 Python 3.13、
标准库、Tcl/Tk 运行时与 24 个共享库一并打进 AppImage。
用 `env -i` 隔离环境验证：GUI 可独立启动，不依赖宿主 Python/tkinter。

### Wayland / gamescope 适配
`AppRun` 按顺序探测 `GAMESCOPE_WAYLAND_DISPLAY` → `WAYLAND_DISPLAY` →
`XDG_SESSION_TYPE` → `DISPLAY`，选择后端；Wayland 会话下若只有 XWayland
可用则自动回退。无图形环境时用 zenity/kdialog 给出可读提示。

### 图标对齐
Unicode 符号宽度因字体而异。解决方式：
1. 只用几何符号（不用 emoji），保证风格统一
2. 用等宽字体（DejaVu Sans Mono）渲染图标列
3. 实测选出宽度一致（11px）的符号集

### 双语：两个语言版本，非对照显示
菜单「设置 → 语言」整体切换。切换后**界面标签与 265 条说明同时换语言**：
- 中文版：hy3 翻译 + 我校对
- 英文版：xenia 官方英文原文（最准确）
语言选择持久化到 `~/.config/xenia-canary-configtool/settings.json`。

## 验证

### 端到端测试（36 项全通过）
`python3 tools/test_e2e.py`

覆盖：往返一致性、schema 覆盖、写入最小性、TOML 语法有效、
未知项保留、双语资源完整性、枚举元数据、预设有效性、导航覆盖。

### AppImage 隔离验证
`bash tools/verify_appimage.sh` — 解包完整性、捆绑解释器独立性、
GUI 在 `env -i` 下启动成功。

### 界面巡检
`bash tools/ui_tour.sh` — 自动遍历各导航大类、分组、搜索、双语切换并截图。

## 翻译流程

1. 我方（hy3 子智能体 `c007bda6`）产出 265 条中文译文
2. 我校对，修正 7 条术语不一致：
   - `片段着色器` → `片段 shader`（shader 家族统一保留英文）
   - `像素着色` → `像素 shader 的着色`
   - `贴图` → `纹理`
   - `配置文件（profile）` → `玩家档案`（Xbox 玩家档案语境）
   - `draw_resolution_scale_y` 补注上游笔误说明
3. 校对结果：265/265 覆盖，无空译，枚举值全部保留

注：hy3 与 hy4 的产出存在已知的上游笔误沿用
（`draw_resolution_scale_y` 原文写作 "width"），按「不增不减」原则照译并加注。

## 待办

- [ ] hy4（`2d68d872`）独立校对结果合并，做交叉验证
- [ ] 交付物迁移到 `/opt/work/DSH团队建设/交付/最终成果/`

## 时间线

| 阶段 | 内容 |
|---|---|
| 1 | 解析参考配置，建立 265 项 schema（22 分组） |
| 2 | 实现保结构 TOML 编辑器并验证 |
| 3 | 搭建 Tk 界面、分类导航、海蓝主题 |
| 4 | 图标统一对齐（等宽字体 + 几何符号集） |
| 5 | 双语言版本接入 |
| 6 | AppImage 打包与运行时捆绑 |
| 7 | 端到端验证（36 项）与界面巡检 |

---

## 追加需求（第二轮）

### 12. d3d12 与 vulkan 是同一个 gpu 项的取值，不是两个分组

**纠正**：我最初把 D3D12 / Vulkan 呈现为「图形后端」大类下的两张平行卡片，
容易让人误以为是二选一的后端选择。实际：

- `GPU.gpu` 是**一个**枚举项，取值 `[any, d3d12, vulkan, null]`，这才是后端选择
- `D3D12` / `Vulkan` 是两个 TOML 分组，存放**各后端专属的细调项**

**实现**：建立依从规则（`navmeta.py`）：

| 规则结构 | 作用 |
|---|---|
| `GROUP_WHEN` | 整个分组只在某取值下显示 |
| `DEPENDENT_KEYS` | 单个设置项只在某取值下显示 |
| `AUTO_VALUES = {any}` | 自动模式下各分支都可能生效，全部显示 |
| `affects_visibility()` | 判定改动是否需重建视图 |

可见性矩阵：

| gpu 取值 | 显示分组 | 列表项数 |
|---|---|---|
| any | D3D12 + Vulkan | 17 |
| d3d12 | 仅 D3D12 | 9 |
| vulkan | 仅 Vulkan | 8 |
| null | 无 | 0 |

**关键点**：
1. 被隐藏的分组不能静默消失 —— 界面给出提示条，说明「需 gpu = xxx」，
   并提示改为 any 可同时显示
2. `apply_editor()` 中若改动的是依从开关，必须 `render_rows()` 整段重建，
   否则用户看到的是过期的可见性
3. 搜索时**不做依从过滤**，否则用户搜不到某个分支的项

### 踩坑：隐藏提示条被网格挤压

提示条最初 `pack` 进卡片区容器 `self.cards_host`，而卡片用 `grid` 排布，
两种布局方式冲突导致提示条被挤到负偏移、文字溢出到可视区外。

修复：提示条放进同级的**独立容器** `notice_host`，并给文字 Label 设
`wraplength` 与 `fill="x"`。

## 翻译校对（hy4 第二校对）

hy4（workbuddy-global/hy4-preview-f）独立校对 265 条，产出 17 条修正。
逐条核实后**采纳 16 条**，1 条保留己见：

**采纳的关键修正**：
- `gpu_allow_invalid_fetch_constants`：我译「类型和无效的」有歧义，
  原文 `fetch constants with invalid type` 应为「类型无效的」
- `depth_float24_convert_in_pixel_shader`：我把同一条件译成前置「在…时」
  + 句尾「前提是…」，重复了，hy4 合并正确
- `mrt_edram_used_range_clamp_to_min`：`modified in any of them` 指多个
  RT 合计区间，我译「其中任意一个」收窄了含义
- `license_mask`：跨行句 `Generally the full version license in / Xbox Live
  Arcade titles.` 被我拆坏并重复，hy4 按原文 6 行重排
- `force_mount_devkit`：我多译了原文没有的「存储」二字

**未采纳**：`draw_resolution_scale_y` 的上游笔误注释。hy4 认为属译者按语
应删；我保留但压缩为最简标注「（上游原文此处写作 width）」，因为上游确实
把 Y 轴比例写成 width，这对使用者是有用信息。

**hy4 的重要结论**：157 条 bool 选项逐条核对 Enable/Disable/Allow/Don't
前缀，**无一处启用↔禁用反转** —— 这是最危险的一类错误，全部正确。

**术语一致性建议**（hy4 提出，未强制改）：
present 的「呈现/显示」混用、frame 的「画面/帧」混用、
console 的「主机」与 host 的「宿主」形近易混。

## 新增验证脚本

- `tools/test_dependency.sh` — 依从可见性界面验证
- 应用层直驱测试 — 验证切值后分组即时增删（不重启程序）

---

## 第三轮：布局自适应重写（用户反馈「内容显示不全」）

### 用户反馈

用户以 1824×1000 截图指出两处内容显示不全：左侧导航分类名只剩尾巴、
右侧列表「已修改」列完全看不见。追加要求：**改为根据窗口大小自动调整**。

### 根因（两个独立缺陷）

1. **列宽计算时机错误**：原代码在创建 Treeview 时一次性算列宽：

   ```python
   avail = self.list_host.winfo_width() or (self.root.winfo_width() - 280)
   ```

   首次渲染时 `winfo_width()` 返回 **1**（控件尚未完成布局），fallback 的
   `root.winfo_width() - 280` 同样不可靠，导致算出的四列总宽（994）超过
   容器实际可绘制宽（998 − 滚动条 18 − 边框），把「已修改」列顶出可视区。

2. **列宽全程只算一次**：窗口缩放后不重算，拖宽或全屏都无效。

另有一处：左栏 `sashpos(0, 260)` 硬编码，中文导航标签右边界实测 259，
**顶格 260 无余量**，字体稍有差异即被裁。

### 修复

| 区域 | 修复前 | 修复后 |
|---|---|---|
| 左栏宽度 | 硬编码 260px | 窗口宽 × 20%，钳制 [220,340]；主区保底 560px |
| 设置项名列 | `(avail-30)×0.46` | `(avail-30-标记列)×0.42` |
| 当前值列 | 剩余 − 26 魔数 | 吃掉全部剩余空间 |
| 已修改列 | 固定 60/74 | 不变（仅一个标记符号，无需伸缩） |
| 卡片列数 | `event.width - 280` 魔数 | `_main_width()` 读真实 sash 位置 |
| 重算时机 | 创建时一次 | `<Configure>` + 60/80ms 双防抖 |

新增 `_main_width()` / `_left_width_for()` 两个方法，三处硬编码魔数
（280、300、26）全部消除，一律从控件实际宽度推算。

**防抖设计**：左栏与列宽各自维护 `_sash_job` / `_col_job` 句柄，
拖动窗口时先 `after_cancel` 旧任务再排新任务，只在停稳后重排一次，
避免连续 resize 事件造成的闪烁与卡顿。

### 实测数据（Xvfb :99）

| 窗口 | 左栏 | 主区 | key 列 | value 列 | 已修改 | 溢出 | 卡片列 |
|---|---|---|---|---|---|---|---|
| 940 | 220 | 720 | 258 | 346 | 60 | −12 ✓ | 3 |
| 1024 | 220 | 804 | 284 | 389 | 60 | −27 ✓ | 4 |
| 1280 | 256 | 1024 | 373 | 520 | 60 | −27 ✓ | 5 |
| 1600 | 320 | 1280 | 478 | 671 | 60 | −27 ✓ | 6 |
| 1824 | 340 | 1484 | 568 | 785 | 60 | −27 ✓ | 6 |

溢出值 = 表格右边界 − 窗口宽，恒为负（有余量）；左栏裁切项 0。

### 踩坑与教训

1. **Tk 的 `winfo_width()` 在布局完成前返回 1**，不能作为尺寸依据。
   可靠做法：`after_idle` 等布局完成，或绑定 `<Configure>` 事件。
2. **编辑事故**：`_apply_sash` 方法定义被误插入 `_build_layout` 函数体
   中间，导致状态栏代码（`status_var` / `modified_var` 创建）被吞进
   `_apply_sash`，触发 `AttributeError: 'ConfigToolApp' object has no
   attribute 'status_var'`。教训：**插入新方法前必须确认插入点位于
   前一个方法的 `def` 之外**，改完立即跑一次启动烟测。
3. **原有隐患暴露**：`load_file()` → `render_rows()` → `update_modified_count()`
   的调用链，在状态栏控件创建前就会执行，`self.modified_var` 尚不存在。
   正常启动路径恰好避开，但任何初始化顺序调整都会触发。已加
   `getattr(var, None)` 保护——**这类"恰好不触发"的顺序依赖是定时炸弹**。
4. **Xvfb 忽略 `geometry()` 请求**：`Xvfb :99 -screen 0 1824x1000x24`
   虽经 `xdpyinfo` 确认生效，但 `root.geometry("940x760")` 实测仍得
   1280 宽。测量必须据实读 `root.winfo_width()`，不可假设请求值生效。

### 构建与验证

- `bash packaging/build.sh` → 16M AppImage
- `bash tools/verify_appimage.sh` 三步全 ✓（解包完整性 / 捆绑解释器独立
  启动 / 隔离环境 AppRun 启 GUI + 截图）
- `tools/test_e2e.py` **36/36 通过**
- `tools/test_dependency.sh` 3 步全 ✓
- **包内 `app.py` 与源码逐字节一致**（`--appimage-extract` 后 `diff`）
- desktop 文件 `Categories` 由 `Game;Emulator;Settings;` 改为
  `Settings;Game;`（`Emulator` 非标准主分类）

### 交付

替换 `/opt/work/DSH团队建设/交付/最终成果/Xenia Canary 配置工具/`
下的旧版：

- 旧 md5 `d2a5e73af4c2c8ca70f51ca9a8b9f015`（布局修复前）
- 新 md5 `bd6b7fe707c811b7788ec7192363e177`
- 使用说明.md md5 `62d915f64804b920272d9321fec83918`（补充自适应布局章节）
- `dist/` 已清空，不留中转副本

---

## 第四轮：真机故障修复（字体 + 列宽 + 行高）

### 用户反馈（真机截图，1927×1115 远程桌面）

1. 设置项那一列的文字**上下叠在一起**
2. 「已修改」列**显示不全**（表头只剩「已修」）
3. 明确澄清：**只有设置项名字叠**，其他文字正常；界面其他部分都是中文，
   设置项名显示英文是正常的（TOML 键名本身不可翻译）

用户点出的「只有设置项叠字」是决定性线索 —— 排除了字体损坏（那会全都坏），
把范围收窄到**行高不足**与**列宽不足**。

### 根因（三个独立缺陷）

**1. 行高写死 26px（叠字的直接原因）**

`theme.py` 里 `rowheight=34 if compact else 26` 是硬编码。CJK 字体行距天生比
拉丁字体大，且系统缩放会进一步放大：

| 字体 | scaling=1.0 | 1.5 | 2.0 |
|---|---|---|---|
| DejaVu Sans | 13 | 18 | 24 |
| Noto Sans CJK SC | 13 | 20 | **26** |

scaling=2.0 时 CJK 字体行距正好 26，与写死的行高相等 → 上下沿贴死 → 叠字。
用户那台机器是 1927×1115 的高分屏，缩放很可能 ≥150%。

**2. `stretch=True` 把算好的列宽覆盖掉（「已修改」被裁的真凶）**

这是本轮最隐蔽的 bug。我在 `_apply_tree_columns()` 里精确算出四列宽度并保证
总和 = 可视宽度，但 Tk 的 Treeview 会把**剩余空间再次分配给 `stretch=True`
的列**，从而覆盖设定的 width，让总和重新膨胀。实测：

```
列合计 998  vs  可绘制 987   →  超出 11px，「已修改」列被顶出可视区
```

关掉全部 `stretch`（四列宽度完全由代码控制）后变为 985 ≤ 987，问题消失。

**3. 滚动条宽度没扣干净**

`tree.winfo_width()` 返回的是**含纵向滚动条区域**的宽度，滚动条是叠在
Treeview 之上的。真正能画列的宽度 = 控件宽 − 滚动条宽。原代码用
`self._tree_sb_w = 18` 这个估值，实际滚动条 `winfo_reqwidth()` 是 13~15，
且这个值本身也随主题变化。改为运行时实测。

另外，原先用 `str(sb.cget("orient")) == "vertical"` 判断方向**永远为假**
（Tcl 对象转字符串后不是这个字面值），改为 `"vertical" in str(...)` 才生效。

### 修复方案

**字体（新增能力）**：构建脚本捆绑 5 个字体文件（DejaVu 拉丁+符号 1.8M，
文泉驿微米黑 5M），AppRun 启动时生成临时 fontconfig 配置注册它们。
AppImage 从 16M 增至 19M。

**行高自适应**：新增 `measure_row_height()`，用
`tkfont.Font.metrics("linespace") + 8` 计算，实测缩放 1.0/1.5/2.0 下
分别为 24/26/32，全部大于字体行距。

**列宽自适应**：新增 `_text_width()` 用字体实测文本宽度；「已修改」列按
表头文字（粗体）实测宽度 + 内边距分配，实测 46/55/64/79（对应四种缩放）；
四列总和强制收敛到可视宽度；关闭全部 stretch。

### 踩坑与教训

1. **`stretch=True` 会静默覆盖手动设置的列宽** —— 这是 Tk Treeview 的
   隐藏行为，文档里不显眼。凡是"自己精确算列宽"的场景都必须 `stretch=False`。
2. **`tree.winfo_width()` 含滚动条区域**，不能当可绘制宽度用。
3. **Tcl 对象不能直接与字符串字面量比较**，`cget("orient")` 必须用
   `in` 包含判断。
4. **窗口销毁前要 `after_cancel` 所有 pending 回调**，否则 Tk 报
   `invalid command name "..._apply_sash"`。已在 `on_quit` 中统一处理。
5. **测试防抖逻辑必须留足真实时间**：`after(80ms)` 不会因为密集调用
   `root.update()` 就触发，第一版测试每个宽度只等 0.22s，误判成"列宽不跟随"。
   改为 `while time.time()-t0 < 0.45s` 的 settle 循环后全部通过。
6. **AppRun 不能"尊重用户 FONTCONFIG_FILE"就跳过注入**：用户配置若指向
   无字体目录，程序照样崩。改为无条件注入（配置里同时列出系统字体目录）。

### 验证

- **宿主零字体环境**（`FONTCONFIG_FILE` 指向不存在的目录，`fc-list` 返回 0）：
  打包版 GUI 正常启动并完整渲染 —— 这是本轮最有说服力的验证
- 缩放 1.0 / 1.25 / 1.5 / 2.0 × 窗口 940 / 1280 / 1920 组合：
  列合计恒比可绘制宽少 2px，「已修改」列全部完整
- 窗口来回缩放（1920→1280→940→1280）列宽正确跟随
- `tools/test_e2e.py` 36/36；`tools/test_dependency.sh` 3/3
- `tools/verify_appimage.sh` 三步全 ✓，日志确认「已注册包内字体」

### 交付

- 新 md5 `cb7ce151c91ec4c6430c27aa4aa0bd1a`（19M）
- 使用说明.md md5 `fd463bc195e168d10debebc007d1215e`

---

## 第五轮：真机反馈 4 项

### 1. 导航项悬停时文字看不清

用户原话「常用设置不选择时是看不清字的」。实测对比度：

| 状态 | 底色 | 文字色 | 对比度 |
|---|---|---|---|
| 正常 | `surface #F5F9FC` | `deep #0E3A5C` | 11.15:1 ✓ |
| 悬停（旧） | `primary_light #2E9BD6` | `deep #0E3A5C` | **3.81:1 ✗** |
| 悬停（新） | `hover #D6E9F6` | `text #0F2433` | 12.76:1 ✓ |

根因：`<Enter>` 只改了背景色，**没同步改文字/图标颜色**。深蓝字压亮蓝底，
低于无障碍 4.5:1 下限。修复：新增 `PALETTE["hover"]` 浅底色，悬停时
文字→`text`、图标→`primary_dark`、计数→`primary_dark`，统一由一个
`_paint()` 内联函数切换，避免以后再次漏改某个部件。

### 2. 没有语言 / 国家的修改

**核实结论：xenia-canary 配置文件里根本没有语言或国家选项。**
`grep -i "language\|region\|country\|locale"` 在整个 reference.config.toml
中零命中（唯一命中是注释里 EDRAM region 一词），schema 265 项同样零命中。
主机区域/语言由游戏与 Xbox 360 系统层决定，模拟器不通过 config.toml 暴露。
与区域相关的只有 `console_type`（主机型号）与 `avpack`（视频输出制式包）。
这是用户预期与软件能力的差异，需在说明里讲清，而不是硬造一个选项。

### 3. 没找到 render_target_path_d3d12 / _vulkan

**核实结论：两项都存在，是依从项按设计隐藏。** 用户截图里 `gpu = "d3d12"`，
所以只显示 D3D12 那条。规则见 `navmeta.DEPENDENT_KEYS`：
d3d12 → 只显 d3d12 项；vulkan → 只显 vulkan 项；any → 两条都显。

已验证搜索路径**不过滤依从项**：`gpu=d3d12` 时搜 `render_target_path`
返回 2 条（含 vulkan 那条）。这是有意设计，避免隐藏项搜不到。

### 4. 增加中文名列 ★

用户要求「在每个设置项旁增加一列简要的中文说明」。

**实现**：新增 `brief` 列，**仅中文版显示**（用户明确要求英文版不显示）。
- 数据：`src/data/names_zh.json`，265 条
- **逐条人工撰写**，不是机械截取

中途试过从 `desc_zh.json` 机械提炼（截首句 + 句式规则），**质量不合格**：
说明文本多是完整句子，截出来是「对非开发者无用」「如果遇到未实现的 PowerPC
指令」这类半截句子，`break_condition_truncate` 还被错配成「数值」。
最终改为在 `tools/names_zh.py` 里逐条撰写，`tools/build_names.py` 负责
校验与 schema 完全对齐（缺一多一都报错退出）后写出数据文件。

命名规范：4~10 个汉字的名词短语；保留 D3D12/Vulkan/XMA/FFX 等专有名词写法。
实测长度：最短 4、中位 7、最长 15。

列分配：`star | key | brief | value | modified`，说明列取 `rest*20%`
并夹在 [70, 180]，压缩顺序为 说明 → 当前值 → 设置项名。
中英切换经 `refresh_brief_column()` 重建 `displaycolumns`。

同时把中文名纳入搜索，输入「各向异性」可直接命中 `anisotropic_override`。

### 顺带修复：退出时 after 任务残留

回归测试暴露出两类报错，均为真实缺陷（用户在真机快速划过列表后关窗口会遇到）：

1. `bad window path name "...!toplevel"` —— tooltip 的 `_show()` 在窗口
   销毁后仍访问 `winfo_reqwidth()`。修复：`_show()` 开头检查
   `winfo_exists()`，取宽高处捕获 `TclError` 后放弃。
2. `invalid command name "...<lambda>"` —— `TreeTooltip` 的 after 任务挂在
   `self.tree` 上，未被 `_cancel_pending_jobs()` 覆盖。修复：给
   `Tooltip`/`TreeTooltip` 各加 `cancel()`，App 侧用 `_register_tip()`
   登记全部实例（导航/卡片重建时自动剔除已销毁的，避免列表无界增长），
   退出时统一取消。实测三档缩放下 68 个实例全部清理干净。

### 验证

- 缩放 1.0/1.5/2.0 × 窗口 940/1280/1920 共 9 组：列合计恒比可绘制宽少 2px，
  中文名列与「已修改」列全部完整，全部 ✓
- 中英切换：中文版 `brief` 可见（合计 985），英文版整列隐藏（合计 972）
- 搜索：`render_target_path` → 2 条；`各向异性` → 1 条；`音频` → 3 条
- `tools/test_e2e.py` 36/36；`tools/test_dependency.sh` 全 ✓
- `tools/verify_appimage.sh` 三步全 ✓；确认 `names_zh.json` 已入包
- 退出三档缩放均无 after 残留报错

### 交付

- 新 md5 `7597723b234495d1d3edb4e3a64ae9fb`（19M）
- 使用说明.md md5 `7d5092d418463163fc93754ccb751602`

---

# 第六轮：[XConfig] 账号国家/语言 + 后端专属项定位修复

## 背景

用户上传了自己的 `xenia.config.toml`（36231 bytes），指令：
「把这个中的语言和国家不进去」→ 紧接「补进去」。

**关键推翻**：上一轮判定「xenia-canary 不暴露语言/国家」是基于 265 项版本 +
`grep -in "language\|region\|country\|locale"` 零命中。用户配置文件实测含
`[XConfig]` 分组与 `user_country = 101`、`user_language = 8`，属新版新增键。
旧结论作废。

## 一、[XConfig] 补入

| 环节 | 改动 |
|---|---|
| schema | 265 → **267 项**，新增 `[XConfig]` 分组（`user_country`、`user_language`，`value_type=int`，默认 `101`/`8`） |
| reference.config.toml | 追加 `[XConfig]` 段（从用户配置原样复制 18 行），265 → 267 项，与 schema 完全同步 |
| 取值表 | 新建 `tools/build_xconfig.py` 从 schema 注释解析 `(\d+)=([A-Za-z]{2})`，配人工表 `COUNTRY`(107)/`LANGUAGE`(16) 生成 `src/data/xconfig_choices.json` |
| i18n | 新增 `lookup(key, raw, lang)`、`choice_labels(key, lang)`；`Resources.xconfig` |
| app | `format_display` 整数分支走 xconfig → `中国台湾 (101)`；新增 `_build_lookup_editor`、`_refresh_editor_display` |
| navmeta | `XConfig` 归入 `system` 大类，图标 `⊕`，简介「上报给主机的账号国家与语言」 |
| 文案 | `names_zh` 267 条（`账号国家 / 地区`、`账号语言`）；`desc_zh` 267 条 |

**重要教训**：`_fill_tree()` 有硬过滤 `if key not in self.doc.index: continue`，
schema 有而配置文件没有的项**不会显示**。因此 schema 与 reference.config.toml
必须同步，否则「加了却看不见」。

## 二、后端专属项定位修复（用户反馈）

用户反馈：「render_target_path_d3d12、render_target_path_vulkan 应该在选择对应
gpu 后显示，现在我怎么都找不到」。

### 复现

设 `gpu = "vulkan"` → `render_target_path_vulkan` 确实出现，但在
**「常用设置 → 图形 (GPU)」**（29 项）里；而用户会去
**「图形后端 → Vulkan」**找，该分组只有 `[Vulkan]` 段的 8 项，**没有它**。

根因：这两项在 toml 里属 `[GPU]` 段（大类 `common`），而「图形后端」大类只含
`[D3D12]`/`[Vulkan]` 两个段，二者没有交集 → 按后端浏览永远找不到。

### 修复

`src/navmeta.py` 给 `DEPENDENT_KEYS` 增加 `also_in` 字段（`"D3D12"`/`"Vulkan"`），
新增 `also_in_section(key)` 与 `section_matches(section, key)`；
`src/app.py` 的 `render_rows` 过滤改为计算 `eff_sec`，使该项在原分组与对应后端
分组**两个位置**都出现，`rows` 记录 `section: eff_sec`。

### 实测（打包版上，三种 gpu 取值）

| gpu | 图形后端 → D3D12 | 图形后端 → Vulkan | 常用设置 → GPU |
|---|---|---|---|
| `d3d12` | 10 项，含 `render_target_path_d3d12` | 隐藏 | 29 项，含 d3d12 项 |
| `vulkan` | 隐藏 | 9 项，含 `render_target_path_vulkan` | 29 项，含 vulkan 项 |
| `any` | 10 项，含 d3d12 项 | 9 项，含 vulkan 项 | 30 项，两条都在 |

无重复条目；搜索 `render_target_path` 仍一次返回两条。

## 三、验证与交付

### 测试

- `tools/test_e2e.py`：**37/37 通过**（原 36 项 + 新增「配置项无遗漏」；
  5 处写死计数 265/533/22 更新为 267/553/23）
- `tools/test_dependency.sh`：3/3 通过
- `tools/verify_appimage.sh`：三步全 ✓

### 端到端实测（打包后的 AppImage）

从解包目录 `/tmp/xc2/squashfs-root/usr/share/xenia-canary-configtool` 加载源码，
走真实下拉框路径：

```
下拉选择「美国 (103)」→ doc 值 103 → is_modified=True
→ _write() → toml: user_country = 103   # User country ID.
→ 自动生成 .bak
```

注释与 `user_language` 行完好无损。

### 中英文两版

| | 中文版 | 英文版 |
|---|---|---|
| 分组名 | 账号区域 | Account region |
| 中文名列 | 显示（账号国家 / 地区） | **整列隐藏** |
| 值显示 | 中国台湾 (101) / 中文 (8) | Taiwan (101) / Chinese (8) |
| 下拉框 | 107 项中文国名 | 107 项英文国名 |

英文版菜单、按钮、详情区均已英文化（`File / Settings / Help`、
`Refresh / Save / Open Config File…`、`Setting details`）。

### 交付

- AppImage md5 `3c35abf819b3f642405b323a131bafb9`（19M，19347960 bytes）
- `使用说明.md` 10686 bytes（md5 `f5736daf2f695ad035b8c27e75396f8e`）
- 已迁移至 `/opt/work/DSH团队建设/交付/最终成果/Xenia Canary 配置工具/`，
  复制 → md5 校验一致 → 删除 `dist/` 中转源，属主 10000:node
- 使用说明两处过时内容已改写：
  - 「关于语言/国家」：旧版写「配置文件没有语言或国家选项」→ 已改为
    `[XConfig]` 分组说明 + 107 国/16 语言对照表 + 下拉框用法
  - 「关于 render_target_path_*」：补充「两个入口」表格

## 四、遗留观察

英文版截图首版出现「菜单栏仍是中文」现象，经查是测试脚本直接赋值 `a.lang='en'`
绕过了 `switch_language()`，**非程序缺陷**；改用 `switch_language('en')` 后
全界面正确英文化。

---

# 第八轮：真机视觉反馈三连修（卡片选中态 / 列宽 / 空分组）

用户上传真机截图（bazzite + Steam Deck），提两点：

1. 「常规设置没被选中是字体颜色不对」
2. 「中文名那列默认不够宽，当前值那列默认太宽了」

排查中另外发现一个**用户没提但更严重**的问题（见第三节）。

## 一、卡片选中态视觉反了

### 现象

用户认为「常规」卡片看起来像没选中。实测发现：

| 状态 | 旧字色 | 白底对比度 |
|---|---|---|
| 选中 | `primary #1B6CA8` | 5.59:1 |
| 未选中 | `deep #0E3A5C` | **11.81:1** |

**未选中的字反而最深最清楚**，选中的反而是浅海蓝 —— 与用户直觉完全相反。
且边框只差 1px→2px，几乎看不出。

### 修复

`_make_card` 改为「选中更重」：

| 状态 | 底色 | 字色 | 对比度 | 字重 | 描边 |
|---|---|---|---|---|---|
| 选中 | `surface_alt #E8F2F9` | `deep #0E3A5C` | 10.40:1 | 加粗 | `primary` 2px |
| 未选中 | `surface_card #FFFFFF` | `primary_dark #12507E` | 8.49:1 | 常规 | `border` 1px |

同时把 `<Leave>` 还原逻辑从 `border_strong` 改为 `primary`，否则鼠标移开后选中边框会退回旧色。

**排查插曲**：一度以为「选中态从未生效」，因为探针显示所有卡片 fg 恒为 deep。
实为探针自己传了中文显示名（`select_section('视频输出')`），而内部键是英文
（`select_section('Video')`）。用正确键复测后，选中态本来是生效的，只是视觉太弱。

## 二、列宽配比失衡

### 现象

中文名列被压到放不下 11 字中文名（截断成「自定义内部显示分…」），
而当前值列拿了大半宽度却只显示「关」「开」一个字符。

### 修复

不再机械按比例切，改为**按实测需求分配**：

- `brief_min` 上限 180 → **260**（容纳最长的中文名）
- 新增 `val_need`：扫描本组所有值，按实测最宽值分配，上限 `avail * 0.30`
- 分配顺序改为 val → brief → key，剩余全给设置项名列
- 压缩顺序改为 key → val → brief（floor 110/70/100）

### 效果（窗口 1500、scaling 2.0）

| 分组 | 中文名 | 当前值 | 设置项 |
|---|---|---|---|
| 常规 | 226 | 212 | 422 |
| 显示输出 | 187 | 256 | 417 |
| 键盘映射 | 142 | 212 | 548 |

「禁用双击切换全屏」等长中文名完整显示。

## 三、整组高级项导致「卡片数 ≠ 实际条数」（新发现）

### 现象

「系统与存储」下 **Kernel 卡片写 16、Logging 卡片写 12，点进去都是空白**。

### 根因

`_fill_tree` 的过滤：

```python
if not query and not self.show_advanced and e.get("advanced") and self.active_nav != "developer":
    continue
```

而Kernel 的 16 项、Logging 的 12 项**全部** `advanced=True`，在「系统与存储」大类下
被整体过滤；但卡片计数用的是 `len(schema["sections"][sec])`，即 schema 总数 → 数字骗人。

### 修复

新增 `_section_visible_count(section) -> (n, reason)` 与 `_is_advanced(key)`（惰性索引），
计数口径与 `_fill_tree` 完全对齐，还需额外算上：

- **依从项**：`render_target_path_*` 会额外出现在对应后端分组下（`also_in_section`）
- **后端可见性**：不适用当前 `gpu` 取值的项被 `key_visible` 隐藏

三处数字统一改为该口径：**卡片计数、左栏分组计数、列表标题**。为 0 时用橙色 `#C8811A` 加粗警示。

另新增空列表说明条（`_render_list_hint_if_empty`）：说明原因 + 「前往开发者选项」按钮。
提示条容器必须 pack 在 `wrap`（expand=True）**之前**，否则会被撑到可视区外看不见；
空态时把列表收成高度 3，有内容时恢复。

### 全量校验

**22 个分组全部吻合，0 组不符。**

插曲：首版 `_section_visible_count` 漏算依从项，导致 GPU 卡片 30/实列 29、D3D12 卡片 9/实列 10；
补上 `also_in_section` 与 `key_visible` 后一致。

## 四、验证与交付

- `tools/test_e2e.py` **38/38 通过**（新增第 [10] 项：遍历全部大类与分组，
  断言 `_section_visible_count(sec)[0] == len(rows)`，防再次脱节）
- `tools/test_dependency.sh` 3/3 通过
- `tools/verify_appimage.sh` 三步全 ✓
- 打包版复验：计数 0 组不符；选中卡片边框恰好 1 个；列宽 key=422/brief=226/value=212/modified=79

### 交付

- AppImage md5 `b1dff7c5448c3e1ee478f6fd8f7e9202`（19352056 bytes）
- 已迁移至 `/opt/work/DSH团队建设/交付/最终成果/Xenia Canary 配置工具/`
- 使用说明新增「关于『某某分组显示 0 项』」章节，功能表补「选中高亮」「计数如实」两行

## 五、教训

1. **颜色语义要跟直觉一致**：选中态必须比未选中更重（更深/有底/更粗），
   反着来即使对比度达标也会让人读错。
2. **屏幕上的数字必须与实际内容同源**：两处独立计算必然漂移。
   这次直接加了遍历式断言把口径钉死。
3. **探针要用与应用相同的内部键**：用显示名去调内部 API 会得到假阴性，
   白白浪费一轮排查。

---

# 第九轮：左栏配色真凶 + 四列宽度规则重定

用户第二次反馈同一现象：「『常规设置』没选中是字体颜色**看不见**」，
并直接指出「你一直修改都没有真正修改到」。用户是对的——前两轮我改错了地方。

## 一、真凶：`select_nav` 只刷背景不刷前景

前两轮我一直在改**卡片**（`_make_card`）的选中配色，但用户截图里消失的是
**左栏大类导航**（`_nav_row` / `select_nav`），两处是完全不同的代码路径。

`select_nav` 原实现：

```python
for gid, row in self.nav_rows.items():
    active = gid == nav_id
    bg = PALETTE["primary_dark"] if active else PALETTE["surface"]
    row.configure(background=bg, highlightbackground=bg)
    for child in row.winfo_children():          # ← 只刷 background
        child.configure(background=bg)
        for sub in child.winfo_children():
            sub.configure(background=bg)        # ← 从不碰 foreground
```

于是切换大类时：

| 时刻 | 「常用设置」前景 | 背景 | 结果 |
|---|---|---|---|
| 初始（选中） | `#FFFFFF` 白 | `#12507E` 深蓝 | 正常 |
| 切到「图形后端」后 | `#FFFFFF` 白（未重置） | `#F5F9FC` 浅底 | **白字浅底，消失** |

实测确认：

```
点击图形后端后：
  common   '常用设置'  fg=#FFFFFF  bg=#F5F9FC   ← 白字浅底
  graphics '图形后端'  fg=#0E3A5C  bg=#12507E   ← 深字深底，也错
```

选中项的深蓝底把深色字盖住，未选中项的浅底把白字盖住——**两项同时都看不清**。

### 修复

新增 `_repaint_nav_row()`，递归把整棵子树按语义重刷前景：

- 纯数字 / `N 项` 计数 → `sfx_fg`；其中 `0` 恒为橙色 `#C8811A`（保持空组警示）
- 单字符 → 图标色 `ic_fg`
- 其余文字 → `fg`

`select_nav` 改为调用它，前景/背景一起重置。

**实测**：切换任意大类后，`fg=#FFFFFF` 只可能出现在 `bg=#12507E` 上，
0 处白字浅底。打包版同样 0 处。

## 二、四列宽度规则重定（用户明确指定）

用户原话：「设置项与中文名列应该差不多宽，并列第一宽，当前值、修改值一样宽，并列第二」，
并追加「要保证能显示全」「总宽度不能太宽」。

### 三轮试错

| 版本 | 规则 | 结果 |
|---|---|---|
| v1 | brief 上限 260 + `rest*0.62` | key 476 / brief 226 —— 差一倍 |
| v2 | 富余全给 key | key 555 / brief 226 —— 差更多 |
| v3 | 平分 + `key_min` 按最长键名 | key 391 / brief 390 ✓ 但总宽撑满 972 |

v3 还有个副作用：`val_min` 用了 `"Auto (Default)"` 实测宽 158px，
把短值组（全是「关」「开」）的当前值列也撑到 158，而「已修改」只要 79 —— 不并列。

### 最终规则

```
① 设置项名列硬保 key_min = 本组最长键名实测宽 + 16，绝不截断
② 当前值 = 已修改。先给键名列留够 key_min，剩余才轮到当前值
   val_w = max(70, min(max(mark_w, val_need), 剩余预算))
③ 设置项 与 中文名 等宽：need = max(key_min, brief_min)
   need ≤ 可用一半 → 两列都取 need
   否则不等宽，键名列优先（中文名截断仍看得懂）
④ 总宽贴合内容，不强行撑满；超可用宽才压缩（顺序：中文名 → 当前值 → 键名）
⑤ minwidth 必须写 = width：minwidth 更大时 Tk 会强制拉宽，破坏贴合
```

### 实测（窗口 1500、scaling 2.0、可用 969）

| 分组 | 设置项 | 中文名 | 当前值 | 已修改 | 总宽 |
|---|---|---|---|---|---|
| 常规 | 321 | 321 | 79 | 79 | 833 |
| 账号区域 | 140 | 140 | 79 | 79 | 471 |
| 存储路径 | 215 | 215 | 79 | 79 | 621 |
| 视频输出 | 392 | 196 | 79 | 79 | 779 |
| 显示输出 | 466 | 138 | 256 | 79 | 972 |

含超长键名/超长值的组必然不等宽，这是内容决定的（`d3d12_allow_variable_refresh_rate_an`
需 392px、`0.20000000298023224` 需 256px）。

## 三、顺带修掉的真缺陷：切换分组不重算列宽

`_apply_tree_columns` 原先只在**窗口 resize** 时触发（`_schedule_col_apply`），
切换分组不触发 → 沿用上一组宽度，出现截断或大片空白。

已在 `_render_settings_list` 末尾加：

```python
self.root.after_idle(lambda: self._apply_tree_columns(refill=False))
```

`refill=False` 避免重复填充列表（列表刚由该方法填过）。
`_apply_tree_columns` 加同名参数，末尾 `if refill: self._fill_tree()`。

## 四、验证

- `tools/test_e2e.py` **41/41 通过**，新增 3 条断言：
  - 设置项列完整显示最长键名
  - 设置项≈中文名、当前值≈已修改（只校验「不该宽时没宽」，长内容组豁免）
  - 列总宽不超过可用宽
- 全量扫描 23 组 × 4 列：键名截断 0 组、总宽越界 0 组
- 打包版复验：左栏白字浅底 0 处、键名截断 0 组、计数不符 0 组
- AppImage md5 `0e29bab127a61ad46f06599f323e8a30`

### 测试自身的两个坑

1. `root = tk.Tk()` 未设 `geometry` → 默认窗口极窄，列被压缩，
   读到 `mark=58` 这种残值，误报失败。必须 `geometry("1500x950")` + `tk scaling 2.0`。
2. 列宽由 `after(80ms)` 防抖重算，读之前必须等真实时间过去（≥0.45s），
   否则读到上一组的旧宽度。

## 五、教训

**用户说「你一直修改都没有修改到」时，要立刻怀疑自己改错了模块。**
前两轮我盯着「卡片选中态」反复调色，用户截图里模糊的却是**左栏**。
`_make_card` 与 `_nav_row` 两套独立的选中渲染，我只改了前者。
正确做法：拿用户截图里的具体文字（「常规设置」）去代码里反查它属于哪个渲染函数。

---

## 第十二轮（2026-10-10 晚）

### 需求
用户反馈「切换的时候要读取半天才显示」，要求定位并优化切分组延迟；
随后追加「设置每次打开自动最大化」。

### 排障：测量伪影
最初用 `import` 截图 + `compare -metric AE` 逐帧判定耗时，得出 2000–3000ms。
**该数字是假的** —— 每轮上百次截图，每次 X 往返 100–300ms，全部计入。
改用应用自身 `perf_counter` 计时（`fn()` 后 `root.update()` + `update_idletasks()`，
取中位）才得到真值：切大类 3.4–7.2ms（正常），**切分组 733–829ms**。

用真机纯 Tk 基准（`/tmp/tktest.py`）对照，确认 Tk 本身不慢：
插入 300 行 12.1ms、清空+重填 7.5ms、改 4 次列宽 5.5ms、改 300 行单元格 6.9ms；
全屏 2880x1546 下 14.6/11.5/9.6/10.3ms；100 次 update 仅 5.4ms。
→ 瓶颈在应用代码，不在 Tk。

### 根因
cProfile 显示 `render_rows` 纯 Python 仅 52ms，其余约 1000ms 落在 Tk C 层。
罪魁是 `render_rows` 每次都会 **destroy + 重建整片卡片区**（8 个 `_make_card`），
而切分组时卡片内容一字未变 —— 纯浪费。

### 修复
1. `render_rows(cards=True)` 拆出 `_render_cards_area()`；`cards=False` 时完全不碰卡片区。
2. `select_section` 改调 `self.render_rows(cards=False)`。
3. 搜索三路径（`_on_search_key` / `on_search` / `clear_search`）同样传 `cards=False`。
4. `_make_card` 内登记角标：`self.card_badges[section] = (cd, card_bg, empty)`。
5. `_refresh_card_badges` 由「重建整片卡片区」改为**就地改一个 Label** 的文字与颜色
   （700ms → 2ms）。
6. `_render_cards_area` 开头 `self.card_badges = {}` 作废登记表，避免就地刷新摸到死控件。
7. 进一步把设置列表也做成可复用：`_settings_ui` 登记控件，`_try_reuse_settings_list()`
   判定能否复用（控件存活 + 语言未变 + 顶部结构一致），能复用则只改标题文字 +
   `_refill_list_reuse()`（清空行 → `_fill_tree` → 空态提示 → 重算列宽），
   不再重建 Treeview / 表头 / 滚动条 / 4 个 bind / 2 个 tooltip。

### 结果
真机：切分组 General 787→265ms、GPU 829→285ms、Display 733→192ms。
用户确认「这次很快」。
本机 Xvfb（`:98`）63–83ms；回归 41 通过 / 0 失败。

### 自动最大化
`_setup_window` 中 `geometry(...)` 之后 `after(120, self._maximize_window)`——
窗口未映射时调 zoomed 会被多数 WM 忽略，必须延后。
`_maximize_window` 依次尝试 `state("zoomed")` → `attributes("-zoomed")` →
`attributes("-fullscreen")`；`_verify_maximized` 在 180ms 后回查
`winfo_width() >= 屏宽-40`，不满足则 `geometry(屏宽x屏高+0+0)` 兜底。
真机实测 `Position: 0,0` / `Geometry: 2880x1620`，满屏生效。
`_maximize_off` 开关供回归测试关闭（测试要固定 1500x950 测列宽分配）。

### 冗余清理
- `_maximize_window` 删掉收集后从未读取的 `ok` 变量；`_verify_maximized` 删掉未使用的 `h`。
- `_settings_ui` 删掉从不读取的 `"sec"`、`"head"` 两个键。
- **修 bug**：复用判定里 `has_bar = "backend_bar" in ui` —— `backend_bar` 是布尔值
  而非键名，`in` 查的是键，恒为 False，导致后端从属提示条的出现/消失判断失效。
  改为 `ui.get("backend_bar") != bool(...)` 按值比较。
- `card_badges` 每条从 4 元组缩为 3 元组（`active` 存进去就被丢弃、后续重算）。
- `_refill_list_reuse` 去掉吞掉 `TclError` 后返回的半清空状态，改用
  `self.tree.delete(*self.tree.get_children())`。

### 交付
`dist/XeniaCanaryConfigTool-1.0.0-x86_64.AppImage`
md5 `07511076a2268d8eea4bbea539690187`，19356152 bytes。
已迁移至 `/opt/work/DSH团队建设/交付/最终成果/Xenia Canary 配置工具/`（md5 校验一致后删源）。
`使用说明.md` 补充「启动自动最大化」与「响应速度」两节。
