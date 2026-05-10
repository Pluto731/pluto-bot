import asyncio
import logging
from bilibili_api import Credential, session as b_session
from bilibili_api.video import Video

from asr import BaseTranscriber
from audio import download_audio, transcode_to_wav
from database import Database

log = logging.getLogger(__name__)


class BilibiliClient:
    def __init__(
        self,
        credential: Credential,
        bot_uid: int,
        db: Database | None = None,
        transcriber: BaseTranscriber | None = None,
        subtitle_min_length: int = 500,
    ):
        self.credential = credential
        self.bot_uid = bot_uid
        self.db = db
        self.transcriber = transcriber
        self.subtitle_min_length = subtitle_min_length

    async def get_sessions(self) -> list[dict]:
        try:
            result = await b_session.get_sessions(credential=self.credential)
            return result.get("session_list") or []
        except Exception as e:
            log.error(f"get_sessions error: {e}")
            return []

    async def get_session_msgs(self, talker_id: int) -> list[dict]:
        try:
            result = await b_session.get_session_msgs(
                talker_id=talker_id,
                credential=self.credential,
            )
            return result.get("messages") or []
        except Exception as e:
            log.error(f"get_session_msgs error: {e}")
            return []

    async def send_message(self, receiver_uid: int, text: str) -> bool:
        try:
            await b_session.send_msg(
                uid=receiver_uid,
                msg_type=b_session.EventType.TEXT,
                content=text,
                credential=self.credential,
            )
            log.info(f"DM sent to {receiver_uid}")
            return True
        except Exception as e:
            log.error(f"send_message error to {receiver_uid}: {e}")
            return False

    async def get_mentions(self) -> list[dict]:
        try:
            result = await b_session.get_at(credential=self.credential)
            return result.get("items") or []
        except Exception as e:
            log.error(f"get_mentions error: {e}")
            return []

    async def get_video_info_and_subtitle(self, bvid: str) -> tuple[dict, str]:
        """拿视频元信息 + 转写文本。
        优先级：缓存 → B 站字幕 → ASR fallback（如果配置了 transcriber）"""
        v = Video(bvid=bvid, credential=self.credential)
        info = await v.get_info()
        title = info.get("title", bvid)
        author = info.get("owner", {}).get("name", "Unknown")
        pages = info.get("pages", [{}])
        cid = pages[0].get("cid", 0)
        duration = info.get("duration", 0)
        mins, secs = divmod(duration, 60)
        meta = {
            "bvid": bvid,
            "title": title,
            "author": author,
            "duration": f"{mins}:{secs:02d}",
            "url": f"https://www.bilibili.com/video/{bvid}",
        }

        # 1. 缓存
        if self.db is not None:
            cached = await self.db.get_transcript(bvid)
            if cached:
                text, source = cached
                log.info(f"transcript cache hit: {bvid} ({source}, {len(text)} chars)")
                return meta, text

        # 2. B 站字幕
        subtitle_text = await self._fetch_subtitle(v, cid)
        if len(subtitle_text) >= self.subtitle_min_length:
            log.info(f"using subtitle for {bvid} ({len(subtitle_text)} chars)")
            if self.db is not None:
                await self.db.save_transcript(bvid, subtitle_text, "subtitle")
            return meta, subtitle_text

        # 3. ASR fallback
        if self.transcriber is None:
            log.info(f"no ASR fallback configured; returning short subtitle ({len(subtitle_text)} chars)")
            return meta, subtitle_text

        log.info(f"subtitle too short ({len(subtitle_text)} chars), falling back to ASR for {bvid}")
        try:
            asr_text = await self._asr_pipeline(bvid)
            if self.db is not None:
                await self.db.save_transcript(bvid, asr_text, "asr")
            return meta, asr_text
        except Exception:
            log.exception(f"ASR pipeline failed for {bvid}")
            return meta, subtitle_text  # 退回原始字幕（哪怕短的）

    async def _asr_pipeline(self, bvid: str) -> str:
        """下载音频 → 转码 → ASR 转写。每一步都可以缓存（文件 mtime）"""
        m4s_path = await download_audio(bvid, self.credential)
        wav_path = transcode_to_wav(m4s_path)
        text = await self.transcriber.transcribe(wav_path)
        return text

    async def _fetch_subtitle(self, v: Video, cid: int) -> str:
        import aiohttp
        # B 站 AI 字幕（ai-zh）有激活机制：首次调用返回空，第二次才有数据
        subtitles: list[dict] = []
        for attempt in range(2):
            player_info = await v.get_player_info(cid=cid)
            subtitles = player_info.get("subtitle", {}).get("subtitles", [])
            if subtitles:
                break
            log.info(f"no subtitles on attempt {attempt + 1}, retrying after 1.5s")
            await asyncio.sleep(1.5)
        log.info(f"subtitles available: {len(subtitles)} ({[s.get('lan') for s in subtitles]})")
        if not subtitles:
            return ""
        # 优先级：UP 主人工中文 > AI 中文 > 任意中文 > 第一个
        priority = ["zh-CN", "zh-Hans", "zh-Hant", "ai-zh"]
        sub = None
        for lan in priority:
            sub = next((s for s in subtitles if s.get("lan") == lan), None)
            if sub:
                break
        if sub is None:
            sub = next((s for s in subtitles if "zh" in s.get("lan", "")), subtitles[0])
        log.info(f"selected subtitle lan={sub.get('lan')}")
        url = "https:" + sub["subtitle_url"]
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url) as resp:
                    if resp.status != 200:
                        log.error(f"subtitle HTTP {resp.status}: {url[:120]}")
                        return ""
                    data = await resp.json(content_type=None)
            lines = [item["content"] for item in data.get("body", [])]
            return "\n".join(lines)
        except Exception:
            log.exception(f"subtitle fetch failed for {url[:120]}")
            return ""
