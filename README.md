# Claude Manage / Claude 管理器

[English](#english) | [中文](#中文)

<img src="electron/icon.png" width="128" height="128" alt="">

---

## English

Claude Manage is a desktop app that gives you a single place to browse, toggle, and edit every piece of your Claude Code setup. If you have ever dug through `~/.claude/` by hand trying to remember which skill you disabled last week, this is for you.

It reads what is already on your machine. Nothing leaves your computer unless you opt into translation.

### What it handles

**Skills** are where most of the time goes. The split-pane layout shows your full list on the left and everything about the selected skill on the right: its description, trigger keywords, invocation path, and every file under it. Click a skill to auto-translate its English description into Chinese (you provide the Baidu API key in Settings). Import from a GitHub URL with one click. Enable or disable a skill by toggling its `SKILL.md` file.

**Plugins** browse by marketplace. Each one shows its version, author, license, and all the skills it bundles. Translation works the same way as skills.

**MCP servers** list out with their command, type, and arguments. Hit "Edit Config" to open the raw `.mcp.json` file and tweak it directly.

**Hooks** group by event type so you can see which commands fire on `PreToolUse`, `PostToolUse`, `Notification`, and so on.

**CLAUDE.md** loads every config file the app can find: global, per-project, and RTK.md. Pick one from the sidebar and edit it live.

**Memory** shows all memory files under `~/.claude/projects/`. Click any row to read the full content.

**Settings** houses four visual themes:

* OLED Dark — the one the app ships with. `#0a0a0a` background, blue accent.
* Clean White — for bright rooms.
* Glass Light — frosted white with `backdrop-filter: blur()`. Needs a wallpaper behind it to show the effect.
* Glass Dark — same glass treatment on a dark base.

Settings also holds the Baidu Translate API fields. The API key stays on disk at `~/.claude/.claude-manage-settings.json` and is masked when the frontend asks for it.

Pages switch with `Ctrl+1` through `Ctrl+8`.

### Install

Go to [Releases](https://github.com/Sisyphus776/claude-manage/releases), download the latest portable ZIP, unzip anywhere, double-click `Claude Manage.exe`.

Requires Windows 10 or later, 64-bit. Claude Code must already be set up on the machine.

### Stack

| Layer | Tech |
|-------|------|
| Shell | Electron 33 |
| Backend | Python 3.10+ talking JSON-RPC 2.0 over stdin/stdout |
| Frontend | Single HTML file with inline CSS and JS. No framework, no build step. |

The Python backend spawns as a child process. The frontend calls `ccm.rpc(method, params)` over Electron's IPC bridge, the main process pipes it to Python, and responses come back the same way.

### Build from source

```bash
# Prerequisites: Node.js 18+, Python 3.10+
pip install pyyaml requests pillow

cd electron
npm install

# Dev mode (set CM_PYTHON env var if needed)
node main.js

# Package
pyinstaller bridge.spec --distpath dist-python --workpath build-tmp --noconfirm
npx electron-builder --dir
```

The icon is generated from `electron/icon.svg` via PIL and injected into the exe with `rcedit`.

### License

MIT © 2026 Sisyphus776

---

## 中文

Claude Manage 是一个桌面工具，用来统一管理本机 Claude Code 的所有配置文件。不用再手动翻 `~\.claude\` 目录找某个 skill 关没关、某个 hook 绑在哪个事件上了。

它只读写你本地的 Claude 配置，不联网。唯一的例外是翻译功能，你主动点才会调百度 API。

### 核心功能

**Skills** 占了日常使用的大头。左边是完整列表，右边展开后能看到一整个 skill 的全部信息：英文描述、中文翻译、触发词、调用路径、文件列表。点任意 skill 自动翻译描述（需在设置里配好百度翻译密钥），翻译结果本地缓存，之后秒开。GitHub 链接一键导入，启用/禁用本质就是把 `SKILL.md` 改个后缀名。

**Plugins** 按来源市场分组，能看到版本号、作者、许可证，以及它带了哪些 skill。翻译逻辑和 skills 一致。

**MCP** 列出所有服务器及其启动命令和参数。点"编辑配置"直接打开 `.mcp.json` 源文件。

**Hooks** 按事件类型归类——`PreToolUse`、`PostToolUse`、`Notification` 等——能看清不同事件上挂了哪些命令。

**CLAUDE.md** 自动找到所有相关文件：全局的、各项目目录下的、以及 RTK.md。侧边栏选一个，右侧编辑器直接改。

**Memory** 扫描 `~\.claude\projects\` 下所有记忆文件，点击查看全文，支持删除。

**设置** 提供四款主题：

* OLED 暗色 — 默认主题，纯黑底 `#0a0a0a`，蓝色强调。
* 纯白 — 适合亮环境。
* 磨砂玻璃亮 — 半透明白底 + `backdrop-filter: blur()`。桌面有壁纸时效果明显。
* 磨砂玻璃暗 — 半透明黑底，同样的毛玻璃质感。

百度翻译 API 密钥也在这里配置。密钥存在 `~\.claude\.claude-manage-settings.json`，传给前端时已做掩码。

页面切换用 `Ctrl+1` 到 `Ctrl+8`。

### 下载

去 [Releases](https://github.com/Sisyphus776/claude-manage/releases) 下载最新便携 ZIP，解压到任意位置，双击 `Claude Manage.exe`。

需要 Windows 10+ 64 位，且本机已安装 Claude Code。

### 技术

| 层 | 技术 |
|---|------|
| 桌面壳 | Electron 33 |
| 后端 | Python 3.10+，通过 stdin/stdout 走 JSON-RPC 2.0 协议 |
| 前端 | 单个 HTML 文件，CSS 和 JS 全部内联，零框架零构建 |

Python 后端作为子进程启动，前端通过 Electron 的 IPC 桥调用 `ccm.rpc()`，主进程转发给 Python，响应原路返回。

### 源码构建

```bash
# 前置：Node.js 18+, Python 3.10+
pip install pyyaml requests pillow

cd electron
npm install

# 开发模式（如 Python 不在 PATH 中，设置 CM_PYTHON 环境变量）
node main.js

# 打包
pyinstaller bridge.spec --distpath dist-python --workpath build-tmp --noconfirm
npx electron-builder --dir
```

应用图标由 `electron/icon.svg` 通过 PIL 渲染生成 `.ico`，再用 `rcedit` 注入 exe。

### 许可证

MIT © 2026 Sisyphus776
