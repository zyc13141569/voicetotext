"""
全局配置。

集中管理音频采集参数、Deepgram 流式参数、全局热键与笔记输出位置，
方便后续调整或接入其他转录引擎。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---- 项目路径 ----
BASE_DIR = Path(__file__).resolve().parent
NOTES_DIR = BASE_DIR / "notes"

# ---- 转录引擎选择 ----
# "deepgram" = 云端流式(需 API Key); "local" = 本地离线 faster-whisper(无需 Key)
ENGINE = os.environ.get("TRANSCRIBER_ENGINE", "deepgram").strip().lower()

# ---- 鉴权 ----
DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "").strip()

# ---- 音频采集参数 ----
# Deepgram 流式推荐 16kHz / 单声道 / 16bit PCM(linear16)
SAMPLE_RATE = 16000
CHANNELS = 1
# 每个音频块约 50ms, 既保证低延迟又不至于过于频繁发送
BLOCKSIZE = 800  # 帧数 = SAMPLE_RATE * 0.05

# ---- Deepgram 流式参数 ----
DG_MODEL = "nova-3"
# 语言: "en"=英文(对中式/印度等口音英语友好) / "multi"=中英混合 / "zh"=中文专用
# 口音偏重时可在 en 与 multi 之间实测取更准者
DG_LANGUAGE = os.environ.get("DG_LANGUAGE", "en").strip()
DG_ENDPOINTING = 100   # 端点检测, 单位 ms (越大越不易断句)
DG_SMART_FORMAT = True
DG_INTERIM_RESULTS = True

# 说话人分离: 给每句标注说话人(说话人1/2...), 切换说话人自动换行
DG_DIARIZE = os.environ.get("DG_DIARIZE", "true").strip().lower() == "true"
# 静默间隙超过该时长(ms)则判定一段话结束, 用于长语音断句(最小 1000)
DG_UTTERANCE_END_MS = int(os.environ.get("DG_UTTERANCE_END_MS", "1000"))

# 关键词提示(Nova-3 keyterm): 专有名词/人名/术语/产品名等模型易错的词。
# 口音重时尤其有用——它能让模型对这些已知词更有把握。
# 限制: 全部 keyterm 合计 <=500 token, 实时场景建议精选 20~50 个最易错的词。
#
# 下面是面向 计算机科学 / 软件设计 / AI 的默认词表(只放容易听错的专有名词/缩写/术语)。
# 你可在 .env 用逗号分隔的 KEYTERMS 追加自己的词, 会与默认词表自动合并去重。
DEFAULT_KEYTERMS = [
    # --- AI / 机器学习 ---
    "LLM", "GPT", "transformer", "embeddings", "tokenizer", "fine-tuning",
    "RAG", "prompt engineering", "neural network", "gradient descent",
    "backpropagation", "hyperparameter", "PyTorch", "TensorFlow",
    "Hugging Face", "RLHF", "quantization", "vector database",
    "attention mechanism", "multimodal", "inference", "diffusion model",
    # --- 计算机科学 / 软件设计 ---
    "Kubernetes", "Docker", "PostgreSQL", "Redis", "GraphQL", "Kafka",
    "gRPC", "WebSocket", "OAuth", "JWT", "microservices", "serverless",
    "middleware", "idempotent", "dependency injection", "design pattern",
    "refactoring", "technical debt", "CI/CD", "polymorphism",
    "encapsulation", "concurrency", "race condition", "time complexity",
    "binary tree", "hash map",
    # --- 编程语言 ---
    "TypeScript", "JavaScript", "Python", "Java", "Rust", "Golang",
    "Kotlin", "Swift", "C++", "C#", "Scala", "Ruby", "PHP",
    # --- 前端开发 ---
    "React", "Vue", "Angular", "Svelte", "Next.js", "Nuxt",
    "Node.js", "Deno", "Bun", "Tailwind", "Sass", "Webpack", "Vite",
    "Babel", "ESLint", "Prettier", "Redux", "Zustand", "JSX",
    "DOM", "CSS", "HTML", "SPA", "SSR", "hydration", "responsive design",
    "accessibility", "npm", "pnpm", "Yarn",
    # --- 后端开发 ---
    "FastAPI", "Django", "Flask", "Express", "Spring Boot", "NestJS",
    "Nginx", "RabbitMQ", "Elasticsearch", "ORM", "SQLAlchemy", "Prisma",
    "REST API", "RPC", "load balancer", "rate limiting", "caching",
    "message queue", "webhook", "cron job", "authentication",
    "authorization", "session", "pagination",
    # --- 云 / DevOps ---
    "AWS", "GCP", "Azure", "Terraform", "Ansible", "Prometheus",
    "Grafana", "Jenkins", "GitHub Actions", "Helm", "Istio",
    "Lambda", "S3", "EC2", "DynamoDB", "observability", "Git",
    # --- 数据库 / 大数据 ---
    "MongoDB", "Cassandra", "MySQL", "SQLite", "Apache Spark", "Flink",
    "ClickHouse", "Snowflake", "ETL", "sharding", "indexing", "replication",
]
_env_keyterms = os.environ.get("KEYTERMS", "").strip()
_extra_keyterms = [w.strip() for w in _env_keyterms.split(",") if w.strip()]
# 合并去重(保持顺序)
DG_KEYTERMS = list(dict.fromkeys(DEFAULT_KEYTERMS + _extra_keyterms))

# ---- 本地引擎 (faster-whisper) 参数 ----
# 模型大小: tiny/base/small/medium/large-v3 (越大越准但越慢)
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small").strip()
# 设备: "auto"/"cuda"/"cpu"; compute_type: "auto"/"int8"/"float16" 等
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "auto").strip()
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "auto").strip()
# 语言: 留空=自动识别(支持中英); 也可固定为 "zh"/"en"
WHISPER_LANGUAGE = os.environ.get("WHISPER_LANGUAGE", "").strip() or None
# 能量 VAD: 静音判定阈值(RMS)与触发定稿的静音时长(秒)
VAD_SILENCE_RMS = 500
VAD_SILENCE_SECONDS = 0.6
# 临时结果最小刷新间隔(秒), 控制本地推理频率
LOCAL_INTERIM_INTERVAL = 0.5

# ---- 全局热键 (pynput GlobalHotKeys 语法) ----
# 切换"监听/待机"
HOTKEY_TOGGLE = "<ctrl>+<alt>+<space>"

# ---- 界面 ----
APP_TITLE = "语音记笔记"

# ---- 网页版服务 ----
WEB_HOST = os.environ.get("WEB_HOST", "127.0.0.1").strip()
WEB_PORT = int(os.environ.get("WEB_PORT", "8000"))

# ---- AI 问答 (支持多家, 均走 OpenAI 兼容接口) ----
# 把记录到的问题发给大模型回答。支持 OpenAI / DeepSeek / Gemini, 配了谁的 Key 就能用谁。
LLM_DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "openai").strip().lower()

# 各家默认接入信息(base_url 均为 OpenAI 兼容的 /chat/completions 前缀)
_LLM_PRESETS = {
    "openai": {
        "label": "OpenAI (ChatGPT)",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_env": "OPENAI_API_KEY",
    },
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "key_env": "DEEPSEEK_API_KEY",
    },
    "gemini": {
        "label": "Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-2.0-flash",
        "key_env": "GEMINI_API_KEY",
    },
    "groq": {
        "label": "Groq (Llama)",
        "base_url": "https://api.groq.com/openai/v1",
        "model": "llama-3.3-70b-versatile",
        "key_env": "GROQ_API_KEY",
    },
}


def _resolve_llm() -> dict:
    """读取各家 Key/模型/base_url, 允许用 {PROVIDER}_MODEL / {PROVIDER}_BASE_URL 覆盖。"""
    result = {}
    for name, preset in _LLM_PRESETS.items():
        up = name.upper()
        result[name] = {
            "label": preset["label"],
            "base_url": os.environ.get(f"{up}_BASE_URL", "").strip() or preset["base_url"],
            "model": os.environ.get(f"{up}_MODEL", "").strip() or preset["model"],
            "key": os.environ.get(preset["key_env"], "").strip(),
        }
    return result


LLM_CONFIG = _resolve_llm()


# ---- 网页端配置(密钥) 持久化与热更新 ----
# 安全说明:
# - 密钥仅保存在服务器本地的 .env 文件(已被 .gitignore 忽略, 不会进 Git/不会上云)。
# - 服务默认只监听 127.0.0.1(本机), 不对外网开放。
# - 后端只会向前端返回"是否已配置 + 末 4 位掩码", 绝不回传明文。
ENV_PATH = BASE_DIR / ".env"

# 允许由网页端配置并写入 .env 的项(其余配置仍只读 .env/环境变量)。
# 自动派生: Deepgram + 默认服务商 + 各家 LLM 的 Key 环境变量名。
MANAGED_SECRETS = (
    ("DEEPGRAM_API_KEY", "LLM_PROVIDER")
    + tuple(p["key_env"] for p in _LLM_PRESETS.values())
)


def reload_secrets() -> None:
    """根据当前环境变量重新计算与密钥相关的配置(供运行时热更新, 免重启)。"""
    global DEEPGRAM_API_KEY, LLM_DEFAULT_PROVIDER, LLM_CONFIG
    DEEPGRAM_API_KEY = os.environ.get("DEEPGRAM_API_KEY", "").strip()
    LLM_DEFAULT_PROVIDER = os.environ.get("LLM_PROVIDER", "openai").strip().lower()
    LLM_CONFIG = _resolve_llm()


def _write_env_file(updates: dict) -> None:
    """把 updates 写入 .env(存在则原地更新, 不存在则追加), 保留其余内容与注释。"""
    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    remaining = dict(updates)
    out = []
    for line in lines:
        stripped = line.lstrip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in remaining:
                out.append(f"{key}={remaining.pop(key)}")
                continue
        out.append(line)
    for key, val in remaining.items():
        out.append(f"{key}={val}")
    ENV_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")


def apply_secrets(updates: dict) -> None:
    """更新内存环境变量并持久化到 .env, 然后热重载相关配置。

    @param updates 仅处理 MANAGED_SECRETS 中的键; 值为空字符串表示清除该项。
    """
    clean = {k: str(v).strip() for k, v in updates.items() if k in MANAGED_SECRETS}
    if not clean:
        return
    for key, val in clean.items():
        os.environ[key] = val
    _write_env_file(clean)
    reload_secrets()


def _mask(value: str) -> str:
    """把密钥转成掩码展示(只保留末 4 位), 绝不返回明文。"""
    value = (value or "").strip()
    if not value:
        return ""
    return "••••" + value[-4:] if len(value) > 4 else "•" * len(value)


def secret_status() -> dict:
    """返回各密钥的 是否已配置 + 掩码 (供前端展示, 不含明文) 以及默认服务商。"""
    status: dict = {
        "deepgram": {"ready": bool(DEEPGRAM_API_KEY), "masked": _mask(DEEPGRAM_API_KEY)},
    }
    for name, conf in LLM_CONFIG.items():
        status[name] = {"ready": bool(conf["key"]), "masked": _mask(conf["key"])}
    status["llm_default"] = LLM_DEFAULT_PROVIDER
    return status
