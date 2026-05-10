"""ASR 后端工厂：按 ASR_BACKEND env 创建对应的 transcriber"""
from .base import BaseTranscriber


def make_transcriber(backend: str, api_key: str, model: str | None = None) -> BaseTranscriber:
    backend = backend.lower()
    if backend == "dashscope_realtime":
        from .dashscope_realtime import DashscopeRealtimeTranscriber
        return DashscopeRealtimeTranscriber(api_key=api_key, model=model or "paraformer-realtime-v2")
    # 预留：whisper / dashscope_async / 别家
    raise ValueError(f"unknown ASR backend: {backend!r}; supported: dashscope_realtime")
