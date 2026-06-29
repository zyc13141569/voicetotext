# 语音转文字记笔记工具

一个 Windows 桌面悬浮小工具：按全局热键开始/停止录音，使用 **Deepgram Nova-3 流式 API** 把
**中英混合**语音在 **1 秒内** 实时转成文字，并自动追加保存为按天归档的 Markdown 笔记。

## 功能特性

- 实时流式转录：边说边出字（临时结果灰色显示，定稿后转为正常颜色）
- 中英混合：`nova-3 + language=multi`，支持中英文 code-switching
- 全局热键：默认 `Ctrl+Alt+Space` 开关监听，任意窗口下可用
- 桌面悬浮窗：无边框、置顶、可拖动
- 自动记笔记：最终文本追加到 `notes/YYYY-MM-DD.md`，支持一键复制 / 清空

## 两种转录引擎（可切换）

在 `.env` 里用 `TRANSCRIBER_ENGINE` 切换：

| 引擎 | 配置 | 是否需要 Key | 特点 |
| --- | --- | --- | --- |
| 云端 Deepgram | `TRANSCRIBER_ENGINE=deepgram` | 需要 | 准确、低延迟、开箱即用 |
| 本地 faster-whisper | `TRANSCRIBER_ENGINE=local` | 不需要 | 离线、隐私好，建议有 NVIDIA 显卡 |

## 一、（方案一）申请 Deepgram API Key

1. 打开 <https://console.deepgram.com/> 注册并登录（新账号赠送额度，足够长期记笔记）。
2. 进入 **API Keys** → **Create a New API Key**，复制生成的 Key。
3. 把项目里的 `.env.example` 复制为 `.env`，填入：

```
TRANSCRIBER_ENGINE=deepgram
DEEPGRAM_API_KEY=你的Key
```

## 一·B、（方案二）使用本地离线引擎

无需任何 API Key，但需要额外安装本地推理库（体积较大）：

```powershell
pip install faster-whisper
```

然后在 `.env` 中设置：

```
TRANSCRIBER_ENGINE=local
WHISPER_MODEL=small        # tiny/base/small/medium/large-v3
WHISPER_DEVICE=auto        # 有显卡填 cuda, 否则 cpu
```

首次运行会自动下载模型。纯 CPU 可用，但要接近 1 秒延迟且准确，建议用 NVIDIA 显卡。

## 二、安装与运行

需要 Python 3.11+。

```powershell
# 在项目根目录
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

提供两种界面，任选其一：

### A. 网页版（推荐，跨平台、最省心）

最简单：**双击根目录的 `start.bat`**，会自动启动服务并打开浏览器。

或手动运行：

```powershell
python -m web.server
```

然后用浏览器打开 <http://127.0.0.1:8000>（端口可用环境变量 `WEB_PORT` 修改）。
点「开始录音」，首次会请求麦克风权限，允许后说话即可实时出字。
页面右上角有状态指示，左下角下拉框可切换「云端 Deepgram / 本地离线」引擎。

> 麦克风在 `localhost`/`127.0.0.1` 下属于安全上下文，可正常使用；
> 如果要从同一局域网的其他设备访问，需要用 HTTPS，否则浏览器会禁用麦克风。

### B. 桌面悬浮窗版

```powershell
python -m src.main
```

启动后出现一个置顶悬浮小窗。点中间大按钮或按 `Ctrl+Alt+Space` 开始/停止。
（桌面版需要额外安装 `sounddevice`、`PySide6`、`pynput`，见 `requirements.txt` 注释。）

## 三、使用说明

| 操作 | 说明 |
| --- | --- |
| `Ctrl+Alt+Space` | 开始 / 停止监听（全局热键） |
| 拖动窗口 | 鼠标左键按住悬浮窗任意空白处拖动 |
| 复制 | 把当前会话文本复制到剪贴板 |
| 清空 | 清空悬浮窗显示（不影响已保存的 Markdown） |

笔记文件位于项目下的 `notes/` 目录，按日期命名，例如 `notes/2026-06-28.md`。

## 三·五、提升识别准确度

- **识别语言 `DG_LANGUAGE`**：`en`（英文，对中式/印度等口音英语友好）、`multi`（中英混合）、`zh`（中文）。口音偏重时建议在 `en` 与 `multi` 之间各测一次取更准的。
- **关键词提示 `KEYTERMS`**：把模型常错的专有名词/人名/术语/产品名（如 `Deepgram,Kubernetes,OKR`）逗号分隔填进 `.env`。口音重时它能让模型对这些已知词更有把握，是性价比最高的提准手段。
- **录音环境**：靠近麦克风、保持安静、用质量好一点的麦克风，影响往往比任何参数都大（网页版已默认开启回声消除+降噪）。

### 长语音断句 与 说话人分离

- **断句**：长时间连续说话时，除了停顿（`speech_final`）会断句外，还会按 `smart_format` 生成的**句末标点**自动分行；`DG_UTTERANCE_END_MS`（默认 1000ms）控制多长静默算一段结束。
- **区分说话人**：`DG_DIARIZE=true` 开启后，多人对话会标注「说话人1 / 说话人2…」，并在说话人切换处自动换行。单人记笔记可设为 `false`。

改完 `.env` 后需重启服务（网页版重新运行 `python -m web.server`）生效。

## 四、常见问题

- **没有声音 / 不出字**：检查系统默认麦克风是否正常，以及 `.env` 中的 Key 是否正确。
- **热键无效**：确认没有其他软件占用 `Ctrl+Alt+Space`，可在 `config.py` 中修改 `HOTKEY_TOGGLE`。
- **延迟偏高**：通常是网络到 Deepgram 的往返延迟，更换更稳定的网络即可。

## 五、项目结构

```
voicetotext/
  requirements.txt
  .env.example
  config.py            # 参数配置
  README.md
  src/
    transcriber.py     # 转录引擎: Deepgram(websockets) + 本地 faster-whisper + 工厂
    notes.py           # Markdown 笔记保存
    audio.py           # 麦克风采集 (桌面版, sounddevice)
    overlay.py         # 悬浮窗 UI (桌面版, PySide6)
    hotkey.py          # 全局热键 (桌面版, pynput)
    main.py            # 桌面版入口
  web/
    server.py          # 网页版后端 (FastAPI + WebSocket)
    static/index.html  # 网页版前端 (麦克风采集 + 实时显示)
```

## 六、后续可扩展

- 转录引擎已抽象为 `Transcriber` 接口，可新增本地离线引擎（如 `faster-whisper`）而不改动 UI 层。
