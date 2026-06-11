# Claude Manage / Claude 管理器

[English](#english) | [中文](#中文)

<img src="electron/icon.png" width="128" height="128" alt="Claude Manage Icon">

---

## English

A local desktop GUI application for viewing and managing all Claude Code components on your machine: Skills, Plugins, MCP Servers, Hooks, CLAUDE.md, and Memory files.

### Features

| Page | Description |
|------|-------------|
| **Dashboard** | At-a-glance component statistics |
| **Skills** | Browse / enable-disable / delete / import from GitHub URL |
| **Plugins** | Browse by marketplace with version info |
| **MCP** | Server list + raw JSON configuration editor |
| **Hooks** | Event-grouped hook viewer |
| **CLAUDE.md** | Multi-file editor for project and global config files |
| **Memory** | View and delete memory files |
| **Settings** | 4 visual themes + Baidu Translate API configuration |

**Theme System:**
- **OLED Dark** — Pure `#0a0a0a` background, blue `#58a6ff` accent
- **Clean White** — Light professional theme
- **Glass Light** — Frosted glass with `backdrop-filter: blur()`
- **Glass Dark** — Dark frosted glass with `backdrop-filter: blur()`

**Translation:** Click any skill or plugin detail to auto-translate its English description to Chinese via Baidu Translate API (API key required, configured in-app).

**Keyboard shortcuts:** `Ctrl+1`~`Ctrl+8` to switch between pages.

### Download

Go to [Releases](https://github.com/dongzhishuai/claude-manage/releases) and download the latest `Claude-Manage-v*-portable.zip`.

Unzip and double-click `Claude Manage.exe` to run. No installation required.

### Requirements

- **Windows 10+ (64-bit)**
- Claude Code installed and configured (`~/.claude/` directory)
- Baidu Translate API key (optional — only needed for auto-translation)

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Desktop Shell | Electron 33 |
| Backend | Python 3.10+ (JSON-RPC 2.0 subprocess) |
| Frontend | Vanilla HTML/CSS/JS, no framework |

### Architecture

```
Electron Main Process
  ├── Spawns bridge.exe (Python, stdin/stdout JSON-RPC 2.0)
  └── BrowserWindow (frameless, transparent)
       ├── preload.js — contextBridge API (ccm.rpc, window controls)
       └── renderer/index.html — all 8 pages, 4 themes, i18n
```

### Build from Source

**Prerequisites:**
- Node.js 18+
- Python 3.10+
- Python packages: `pip install pyyaml requests pillow`

**Development:**
```bash
cd electron
npm install
# Set CM_PYTHON env var if needed (defaults to 'python')
node main.js
```

**Build release:**
```bash
# 1. Build Python backend
cd electron
pyinstaller bridge.spec --distpath dist-python --workpath build-tmp --noconfirm

# 2. Build Electron app
npx electron-builder --dir

# 3. Generate icon and inject
python -c "..."  # generates icon.ico from icon.svg
node -e "require('rcedit')..."  # injects icon into exe

# 4. Create portable ZIP
powershell Compress-Archive ...
```

### FAQ

**Q: My Baidu API key is in `~/.claude/.claude-manage-settings.json`. Will it leak?**
A: No. That file is outside the project directory. It's never committed to git. The app reads it locally and masks it when sent to the frontend.

**Q: Can I share this with others?**
A: Yes. Zip the app directory and send it. Each user sees their own Claude configuration.

**Q: Does it work on macOS/Linux?**
A: Currently Windows-only. The Electron shell and Python backend should work cross-platform but haven't been tested.

### License

MIT © 2026 董智帅

---

## 中文

一款本地桌面 GUI 应用，用于查看和管理本机 Claude Code 全部组件：Skills、Plugins、MCP 服务器、Hooks、CLAUDE.md、Memory 文件。

### 功能介绍

| 页面 | 说明 |
|------|------|
| **仪表盘** | 所有组件数量一览 |
| **Skills** | 浏览 / 启用禁用 / 删除 / 从 GitHub URL 一键导入 |
| **Plugins** | 按市场分组查看，显示版本和作者信息 |
| **MCP** | 服务器列表 + 原始 JSON 配置编辑器 |
| **Hooks** | 按事件类型分组展示 |
| **CLAUDE.md** | 多文件编辑器，支持全局和项目级配置文件 |
| **Memory** | 记忆文件查看与删除 |
| **设置** | 四款主题切换 + 百度翻译 API 配置 |

**四款主题：**
- **OLED 暗色** — 纯黑底 `#0a0a0a`，蓝色 `#58a6ff` 点缀
- **纯白** — 干净明亮的专业主题
- **磨砂玻璃亮** — 半透明白色 + `backdrop-filter: blur()` 模糊
- **磨砂玻璃暗** — 半透明黑色 + `backdrop-filter: blur()` 模糊

**中文翻译：** 点击任意 Skill 或 Plugin 详情，自动将英文描述翻译为中文（需先在设置中配置百度翻译 API 密钥）。

**键盘快捷键：** `Ctrl+1`~`Ctrl+8` 切换页面。

### 下载与使用

前往 [Releases](https://github.com/dongzhishuai/claude-manage/releases) 下载最新版 `Claude-Manage-v*-portable.zip`。

解压后双击 `Claude Manage.exe` 即可运行。无需安装。

### 环境要求

- **Windows 10 及以上（64 位）**
- 已安装并配置 Claude Code（存在 `~\.claude\` 目录）
- 百度翻译 API 密钥（可选 — 仅自动翻译功能需要）

### 技术栈

| 层 | 技术 |
|---|------|
| 桌面壳 | Electron 33 |
| 后端 | Python 3.10+ (JSON-RPC 2.0 子进程通信) |
| 前端 | 纯 HTML/CSS/JS，无框架，零依赖 |

### 架构

```
Electron 主进程
  ├── 启动 bridge.exe（Python 后端，stdin/stdout JSON-RPC 2.0 协议）
  └── BrowserWindow（无边框，透明，圆角）
       ├── preload.js — contextBridge 安全桥接
       └── renderer/index.html — 8 个页面 + 4 款主题 + 中英双语
```

### 源码构建

**前置条件：**
- Node.js 18+
- Python 3.10+
- Python 包：`pip install pyyaml requests pillow`

**开发模式：**
```bash
cd electron
npm install
# 如 Python 不在 PATH 中，可设置 CM_PYTHON 环境变量
node main.js
```

**发布打包：**
```bash
# 1. 构建 Python 后端
cd electron
pyinstaller bridge.spec --distpath dist-python --workpath build-tmp --noconfirm

# 2. 构建 Electron 应用
npx electron-builder --dir

# 3. 生成图标并注入 exe
# icon.ico 从 icon.svg 通过 PIL 渲染生成，用 rcedit 注入 exe

# 4. 创建便携 ZIP
powershell Compress-Archive ...
```

### 常见问题

**问：我的百度 API 密钥存在 `~\.claude\.claude-manage-settings.json`，会泄露吗？**
答：不会。该文件不在项目目录内，不会被 git 提交。程序读取后传给前端时已做掩码处理。

**问：可以发给别人用吗？**
答：可以。把程序目录打包成 zip 发给对方。每个用户看到的是自己电脑上的 Claude 配置。

**问：支持 macOS/Linux 吗？**
答：目前仅 Windows。Electron 和 Python 后端本身跨平台，但未做适配测试。

**问：程序会联网吗？**
答：仅在用户主动使用翻译功能时，调用百度翻译 API。其他所有操作均为本地读写，不发送任何数据。

### 许可证

MIT © 2026 董智帅
