"""ffmpeg 转码：m4s/mp4 → 16kHz mono wav（paraformer 标准输入）"""
import logging
import subprocess
from pathlib import Path

import imageio_ffmpeg

log = logging.getLogger(__name__)


def transcode_to_wav(input_path: Path, max_seconds: int | None = None) -> Path:
    """转码为 16kHz mono wav。max_seconds 可截前 N 秒（用于测试）。

    输出路径 = input_path.with_suffix('.wav')，已存在且大小匹配则跳过"""
    wav_path = input_path.with_suffix(".wav")
    if wav_path.exists() and max_seconds is None and wav_path.stat().st_size > 1024:
        log.info(f"wav cache hit: {wav_path.name}")
        return wav_path

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-i", str(input_path), "-ar", "16000", "-ac", "1"]
    if max_seconds is not None:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-y", str(wav_path)]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        err = result.stderr.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"ffmpeg failed: {err}")

    size_mb = wav_path.stat().st_size / 1024 / 1024
    log.info(f"transcoded: {input_path.name} -> {wav_path.name} ({size_mb:.1f} MB)")
    return wav_path
