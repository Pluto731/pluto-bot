"""下载 B 站 dash audio 流，保存为 .m4s 文件"""
import logging
import os
from pathlib import Path

import aiohttp
from bilibili_api import Credential
from bilibili_api.video import Video

log = logging.getLogger(__name__)

CACHE_DIR = Path(os.getenv("AUDIO_CACHE_DIR", "./data/cache"))

_HEADERS = {
    "Referer": "https://www.bilibili.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


async def download_audio(bvid: str, credential: Credential) -> Path:
    """下载 B 站视频音频流到 CACHE_DIR/{bvid}.m4s，已存在则直接返回路径"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CACHE_DIR / f"{bvid}.m4s"
    if out_path.exists() and out_path.stat().st_size > 1024:
        log.info(f"audio cache hit: {out_path.name}")
        return out_path

    v = Video(bvid=bvid, credential=credential)
    info = await v.get_info()
    cid = info["pages"][0]["cid"]

    download_url = await v.get_download_url(cid=cid)
    audios = download_url.get("dash", {}).get("audio", [])
    if not audios:
        raise RuntimeError(f"no audio stream for {bvid}")
    audio_url = audios[0]["baseUrl"]

    async with aiohttp.ClientSession(headers=_HEADERS) as session:
        async with session.get(audio_url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"audio download HTTP {resp.status} for {bvid}")
            with open(out_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    f.write(chunk)

    size_mb = out_path.stat().st_size / 1024 / 1024
    log.info(f"audio downloaded: {bvid} -> {out_path.name} ({size_mb:.1f} MB)")
    return out_path
