# 使用指南 / How to Use（零基础一步步复刻）

这是一个**实时语音转文字记笔记**工具：打开网页，点「开始录音」，说话即可实时转成文字，
并自动按天保存成 Markdown 笔记。支持中英混合、专业术语优化、长语音自动断句、多说话人区分。

下面的步骤**假设你电脑上什么都没装**，跟着做即可完整复刻。

---

## 0. 你需要准备什么

- 一台 Windows / macOS / Linux 电脑
- 一个能联网的浏览器（Chrome / Edge / Firefox 等）
- 一个麦克风
- 一个 Deepgram 账号（免费注册，送额度，下面有步骤）

---

## 1. 安装 Python（3.11 或更高）

1. 打开 <https://www.python.org/downloads/> 下载并安装。
2. **Windows 安装时务必勾选 “Add Python to PATH”**。
3. 安装完成后，打开终端验证：

```bash
python --version
```

看到 `Python 3.11.x`（或更高）即可。

> Windows 打开终端：按 `Win + R`，输入 `powershell`，回车。

---

## 2. 获取项目代码

如果你装了 Git：

```bash
git clone https://github.com/<你的用户名>/<你的仓库名>.git
cd <你的仓库名>
```

没装 Git 也可以：在 GitHub 仓库页面点 **Code → Download ZIP**，解压后进入该文件夹。

---

## 3. 安装依赖

> **Windows 用户最省事**：可以**跳过本节**，直接双击根目录的 **`start.bat`**。
> 它会自动检查 Python、创建虚拟环境、安装依赖、生成 `.env` 并启动——见下面第 6 节。
> 只有想手动安装、或用 macOS/Linux 时才需要本节。

在项目根目录下执行（推荐用虚拟环境，避免污染系统）：

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

> 说明：网页版只需要 `requirements.txt` 里默认启用的几个包即可。
> 桌面悬浮窗版（可选）需要额外安装 `sounddevice`、`PySide6`、`pynput`（见 `requirements.txt` 里的注释）。

---

## 4. 申请 Deepgram API Key（免费）

1. 打开 <https://console.deepgram.com/> 注册并登录（新账号赠送额度，日常记笔记基本用不完）。
2. 左侧进入 **API Keys** → 点 **Create a New API Key**。
3. 复制生成的 Key（它只会完整显示一次，请妥善保存）。

---

## 5. 配置你的 Key

1. 把项目里的 `.env.example` 复制一份，改名为 `.env`。

   - Windows：`copy .env.example .env`
   - macOS / Linux：`cp .env.example .env`

2. 用记事本/编辑器打开 `.env`，把第二行改成你的 Key：

```ini
DEEPGRAM_API_KEY=在这里粘贴你自己的Key
```

> `.env` 已经被 `.gitignore` 忽略，**不会被上传到 GitHub**，请放心填写。
> 千万不要把真实 Key 写进任何会提交的文件里。

---

## 6. 启动

### 方式 A：双击启动（Windows，最简单，推荐）

直接双击根目录的 **`start.bat`** 即可。**首次运行**它会自动完成全部环境准备：

1. 检查是否装了 Python（没装会提示你去下载）；
2. 自动创建虚拟环境 `.venv`；
3. 自动安装所需依赖（这一步首次会下载，约 1~3 分钟，请耐心等）；
4. 若没有 `.env` 会自动生成一份；
5. 启动服务并自动打开浏览器。

之后再次双击会**跳过安装、秒开**（依赖有更新时才会自动重装）。
连 Key 都可以等启动后在网页右上角 ⚙ 里填，真正做到"双击即用"。

### 方式 B：命令行启动（全平台）

```bash
python -m web.server
```

然后浏览器打开：<http://127.0.0.1:8000>

---

## 7. 开始使用

1. 点页面上的「**开始录音**」按钮。
2. 浏览器会请求**麦克风权限**，点「允许」。
3. 开始说话——文字会实时出现（灰色是临时结果，定稿后变白色，每句一行）。
4. 再点「停止录音」结束。
5. 笔记自动保存在项目下的 `notes/` 目录里，按日期命名（如 `notes/2026-06-29.md`）。

页面按钮说明：

| 按钮 | 作用 |
| --- | --- |
| 开始 / 停止录音 | 开关实时转录 |
| 云端 Deepgram / 本地离线 | 切换转录引擎 |
| 复制 | 复制当前会话文字到剪贴板 |
| 清空 | 清空当前显示（不影响已保存的笔记） |

---

## 8. 个性化设置（都在 `.env` 里改，改完重启服务生效）

| 配置项 | 作用 | 示例 |
| --- | --- | --- |
| `DG_LANGUAGE` | 识别语言：`en` 英文 / `multi` 中英混合 / `zh` 中文 | `DG_LANGUAGE=en` |
| `KEYTERMS` | 追加专业词汇，提升专有名词准确度（逗号分隔） | `KEYTERMS=Composer,LangChain,你的项目名` |
| `DG_DIARIZE` | 是否区分说话人（标注「说话人1/2…」） | `DG_DIARIZE=true` |
| `WEB_PORT` | 网页服务端口（默认 8000） | `WEB_PORT=8000` |
| `LLM_PROVIDER` | 默认 AI 服务商：`openai`/`deepseek`/`gemini` | `LLM_PROVIDER=openai` |
| `OPENAI_API_KEY` 等 | 各家 AI 的 Key（见下方） | 见下方说明 |

### 问 AI（可选，支持 OpenAI / DeepSeek / Gemini）

录完一段内容后，点页面上的「问 AI」把它作为问题发给大模型回答，可选「简略 / 详细」，
并可在「AI 服务商」下拉里切换用哪家（你配了哪几家的 Key，就能选哪几家）。

**推荐方式（网页配置）**：启动后点页面右上角 ⚙「API 配置」，直接填入各家 Key 并保存，
**立即生效、无需重启**。密钥只会写入本机的 `.env`（已被 Git 忽略），页面只显示末 4 位掩码、
绝不回显完整密钥，服务也只监听本机 127.0.0.1，安全可控。

也可手动填入任意一家（或多家）的 Key 到 `.env`：

```ini
# 三选一或都填；默认用 LLM_PROVIDER 指定的那家
OPENAI_API_KEY=你的OpenAI Key       # 申请 https://platform.openai.com/api-keys
DEEPSEEK_API_KEY=你的DeepSeek Key    # 申请 https://platform.deepseek.com/api_keys
GEMINI_API_KEY=你的Gemini Key        # 申请 https://aistudio.google.com/apikey
GROQ_API_KEY=你的Groq Key            # 免费/极快, 申请 https://console.groq.com/keys
```

重启服务即可。未配置任何 Key 时该功能会提示你去配置，不影响转录功能。

> 原理：DeepSeek、Gemini 都提供「OpenAI 兼容」接口，所以三家用同一套调用方式，随时可切换。

### 音频来源：麦克风 / 电脑播放声音

页面「音频来源」可切换：
- **麦克风**：录你说的话。
- **电脑播放声音**：转录电脑里正在播放的音频（视频、会议、直播等）。点开始后在弹窗里
  选择标签页或屏幕，并**勾选「分享标签页音频 / 系统音频」**（Chrome / Edge 支持最好）。

> 项目已内置了一批 计算机科学 / 软件设计 / AI 常用术语作为默认关键词，
> 你在 `KEYTERMS` 里填的会和它们自动合并。

---

## 9. 本地离线模式（可选，无需 API Key / 不联网）

如果你不想用云端、想完全离线（建议有 NVIDIA 显卡，否则较慢）：

```bash
pip install faster-whisper
```

在 `.env` 里设置：

```ini
TRANSCRIBER_ENGINE=local
WHISPER_MODEL=small
WHISPER_DEVICE=auto
```

然后照常启动即可（首次运行会自动下载模型）。

---

## 10. 常见问题

- **不出字 / 没反应**：检查 `.env` 里的 Key 是否填对、麦克风是否被浏览器允许、麦克风是否是系统默认设备。
- **页面打不开**：确认终端里看到 `Uvicorn running on http://127.0.0.1:8000`；端口被占用就在 `.env` 改 `WEB_PORT`。
- **中文不准**：把 `DG_LANGUAGE` 在 `en` 和 `multi` 之间各试一次，取更准的；并尽量靠近麦克风、保持安静。
- **多人同时说话分不开**：这是单声道实时分离的固有限制，轮流说话效果更好；要精确区分需每人一个独立麦克风。

---

## 11. 项目结构速览

```
.
├─ start.bat            # Windows 一键启动
├─ requirements.txt     # 依赖清单
├─ .env.example         # 配置模板（复制为 .env 后填 Key）
├─ config.py            # 所有可调参数
├─ web/                 # 网页版（推荐）
│   ├─ server.py        # 后端：FastAPI + WebSocket
│   └─ static/index.html# 前端页面
└─ src/                 # 核心逻辑 + 桌面版
    ├─ transcriber.py   # 转录引擎（Deepgram / 本地）
    ├─ notes.py         # 笔记保存
    ├─ audio.py / overlay.py / hotkey.py / main.py  # 桌面悬浮窗版
```

祝使用愉快！
