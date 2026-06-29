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
    # --- 语言 / 框架 / 工具 ---
    "TypeScript", "Rust", "Golang", "FastAPI", "React", "Node.js",
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
