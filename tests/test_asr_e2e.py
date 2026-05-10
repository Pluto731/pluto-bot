"""端到端 ASR 测试：B 站 BV → 下载音频 → ffmpeg 转码 → paraformer 转写 → 打印结果

用法:
    python tests/test_asr_e2e.py [BV号]
默认 BV1Z44y147xA（王木头·L1/L2 正则化讲解，28 min）"""
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import aiohttp
import imageio_ffmpeg
from bilibili_api import Credential
from bilibili_api.video import Video

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


async def download_audio(bvid: str) -> tuple[Path, dict]:
    """下载 B 站音频流（只下 audio，不下 video）"""
    cred = Credential(
        sessdata=os.environ["BILI_SESSDATA"],
        bili_jct=os.environ["BILI_BILI_JCT"],
        buvid3=os.environ["BILI_BUVID3"],
    )
    v = Video(bvid=bvid, credential=cred)
    info = await v.get_info()
    cid = info["pages"][0]["cid"]

    meta = {
        "bvid": bvid,
        "title": info["title"],
        "author": info["owner"]["name"],
        "duration_sec": info["duration"],
    }
    print(f"[1/3] download")
    print(f"   bvid={bvid}  title={meta['title']!r}")
    print(f"   author={meta['author']}  duration={meta['duration_sec']}s")

    download_url = await v.get_download_url(cid=cid)
    audios = download_url.get("dash", {}).get("audio", [])
    if not audios:
        raise RuntimeError(f"no audio stream for {bvid}")
    audio_url = audios[0]["baseUrl"]

    out_path = CACHE_DIR / f"{bvid}.m4s"
    headers = {
        "Referer": "https://www.bilibili.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
    t0 = time.time()
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(audio_url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"audio HTTP {resp.status}")
            with open(out_path, "wb") as f:
                downloaded = 0
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    f.write(chunk)
                    downloaded += len(chunk)
    print(f"   downloaded {downloaded / 1024 / 1024:.2f} MB in {time.time() - t0:.1f}s -> {out_path.name}")
    return out_path, meta


def transcode_to_wav(m4s_path: Path, max_seconds: int | None = None) -> Path:
    """ffmpeg 转码：m4s -> 16kHz mono wav（paraformer 标准输入）

    max_seconds: 截前 N 秒（用于快速测试）"""
    print(f"\n[2/3] transcode (16kHz mono wav, max_sec={max_seconds})")
    wav_path = m4s_path.with_suffix(".wav")
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [ffmpeg, "-i", str(m4s_path), "-ar", "16000", "-ac", "1"]
    if max_seconds is not None:
        cmd += ["-t", str(max_seconds)]
    cmd += ["-y", str(wav_path)]
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=False)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode('utf-8', errors='replace')[-500:]}")
    print(f"   converted in {time.time() - t0:.1f}s -> {wav_path.name} ({wav_path.stat().st_size / 1024 / 1024:.2f} MB)")
    return wav_path


def transcribe_paraformer(wav_path: Path) -> str:
    """调用 paraformer 转写。两条路径试一下，看 dashscope SDK 哪个能用本地文件"""
    print(f"\n[3/3] paraformer ASR")
    import dashscope

    dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

    # 尝试用 Recognition 流式接口（callback 模式）
    from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

    collected: list[str] = []

    class Cb(RecognitionCallback):
        def on_event(self, result: RecognitionResult):
            sentence = result.get_sentence()
            if not sentence or "text" not in sentence:
                return
            # 只在句子完整结束时才收集，避免 partial 增量重复
            if RecognitionResult.is_sentence_end(sentence):
                collected.append(sentence["text"])
                # 实时打印，方便看进度
                print(f"   [{len(collected):03d}] {sentence['text']}", flush=True)

        def on_error(self, result):
            print(f"   ASR error: {result.message}", flush=True)

        def on_close(self):
            pass

        def on_open(self):
            pass

    recognition = Recognition(
        model="paraformer-realtime-v2",
        format="wav",
        sample_rate=16000,
        callback=Cb(),
        language_hints=["zh"],
    )
    t0 = time.time()
    recognition.start()

    # 把 wav 切片喂进去（paraformer-realtime-v2 是流式协议）
    with open(wav_path, "rb") as f:
        while True:
            chunk = f.read(3200)  # 100ms @ 16kHz 16bit mono
            if not chunk:
                break
            recognition.send_audio_frame(chunk)

    recognition.stop()
    print(f"   ASR done in {time.time() - t0:.1f}s, {len(collected)} sentences")
    return "\n".join(collected)


async def main():
    bvid = sys.argv[1] if len(sys.argv) > 1 else "BV1Z44y147xA"
    print(f"=== ASR E2E test for {bvid} ===\n")
    overall = time.time()

    # 取命令行第二个参数作为截取秒数（默认 60 秒做快速测试）
    max_sec = int(sys.argv[2]) if len(sys.argv) > 2 else 60

    m4s_path, meta = await download_audio(bvid)
    wav_path = transcode_to_wav(m4s_path, max_seconds=max_sec)
    transcript = transcribe_paraformer(wav_path)

    print(f"\n=== TRANSCRIPT ({len(transcript)} chars) ===")
    print(transcript[:2000])
    if len(transcript) > 2000:
        print(f"... (+{len(transcript) - 2000} chars more)")

    out_md = CACHE_DIR / f"{bvid}.transcript.txt"
    out_md.write_text(transcript, encoding="utf-8")
    print(f"\n=== SAVED to {out_md} ===")
    print(f"=== TOTAL {time.time() - overall:.1f}s ===")


if __name__ == "__main__":
    asyncio.run(main())
