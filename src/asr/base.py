"""ASR 抽象接口"""
from abc import ABC, abstractmethod
from pathlib import Path


class BaseTranscriber(ABC):
    """语音转文字接口。所有后端（dashscope / whisper / 别家）都实现这个"""

    @abstractmethod
    async def transcribe(self, wav_path: Path) -> str:
        """输入 16kHz mono wav 路径，输出转写文本（句子用 \\n 分隔）"""
        raise NotImplementedError
