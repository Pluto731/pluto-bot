"""阿里百炼 paraformer-realtime-v2 后端实现

注意：流式接口本质是按近实时速度处理（约 2.5-4x 实时），不适合特别长的音频。
长视频生产场景应该用 paraformer-v2 异步任务接口（DashscopeAsync，TBD）。"""
import asyncio
import logging
from pathlib import Path

import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

from .base import BaseTranscriber

log = logging.getLogger(__name__)


class DashscopeRealtimeTranscriber(BaseTranscriber):
    def __init__(self, api_key: str, model: str = "paraformer-realtime-v2"):
        dashscope.api_key = api_key
        self.model = model

    async def transcribe(self, wav_path: Path) -> str:
        # dashscope SDK 是同步接口，跑在线程池里避免阻塞 event loop
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, wav_path)

    def _transcribe_sync(self, wav_path: Path) -> str:
        collected: list[str] = []

        class Cb(RecognitionCallback):
            def on_event(self, result: RecognitionResult):
                sentence = result.get_sentence()
                if not sentence or "text" not in sentence:
                    return
                if RecognitionResult.is_sentence_end(sentence):
                    collected.append(sentence["text"])

            def on_error(self, result):
                log.error(f"paraformer error: {result.message}")

            def on_close(self):
                pass

            def on_open(self):
                pass

        recognition = Recognition(
            model=self.model,
            format="wav",
            sample_rate=16000,
            callback=Cb(),
            language_hints=["zh"],
        )
        recognition.start()
        with open(wav_path, "rb") as f:
            while True:
                chunk = f.read(3200)
                if not chunk:
                    break
                recognition.send_audio_frame(chunk)
        recognition.stop()
        log.info(f"paraformer transcribed: {wav_path.name} -> {len(collected)} sentences")
        return "\n".join(collected)
