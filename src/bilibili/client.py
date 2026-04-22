import logging
from bilibili_api import Credential, session as b_session, notification as b_notif
from bilibili_api.video import Video

log = logging.getLogger(__name__)


class BilibiliClient:
    def __init__(self, credential: Credential, bot_uid: int):
        self.credential = credential
        self.bot_uid = bot_uid

    async def get_sessions(self) -> list[dict]:
        try:
            result = await b_session.get_sessions(
                credential=self.credential,
                session_type=b_session.SessionType.UNREAD_CHAT,
            )
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
            result = await b_notif.get_at(credential=self.credential)
            return result.get("items") or []
        except Exception as e:
            log.error(f"get_mentions error: {e}")
            return []

    async def get_video_info_and_subtitle(self, bvid: str) -> tuple[dict, str]:
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
        subtitle_text = await self._fetch_subtitle(v, cid)
        return meta, subtitle_text

    async def _fetch_subtitle(self, v: Video, cid: int) -> str:
        try:
            player_info = await v.get_player_info(cid=cid)
            subtitles = player_info.get("subtitle", {}).get("subtitles", [])
            if not subtitles:
                return ""
            sub = next(
                (s for s in subtitles if "zh" in s.get("lan", "")),
                subtitles[0],
            )
            url = "https:" + sub["subtitle_url"]
            import aiohttp
            async with aiohttp.ClientSession() as sess:
                async with sess.get(url) as resp:
                    data = await resp.json(content_type=None)
            lines = [item["content"] for item in data.get("body", [])]
            return "\n".join(lines)
        except Exception as e:
            log.warning(f"subtitle fetch failed: {e}")
            return ""
