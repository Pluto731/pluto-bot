import asyncio
import logging
import sys
from config import Config
from database import Database
from bilibili.client import BilibiliClient
from bilibili.parser import extract_bv, extract_email
from generators.notes import NoteGenerator
from senders.email import EmailSender

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("/app/logs/pluto.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("pluto-bot")

HELP_MSG = (
    "你好！我是 Pluto Bot 📚\n\n"
    "发给我 B 站视频链接或 BV 号，我会生成学习笔记发到你的邮箱~\n\n"
    "使用方法：\n"
    "1️⃣ 先发你的邮箱地址（如 abc@gmail.com）\n"
    "2️⃣ 再发视频链接或 BV 号\n\n"
    "记得随时呼叫 Pluto Bot 哦！💙"
)


class PlutoBot:
    def __init__(self):
        self.cfg = Config()
        self.db = Database()
        self.bili = BilibiliClient(self.cfg.credential, self.cfg.bot_uid)
        self.gen = NoteGenerator(self.cfg.deepseek_api_key, self.cfg.deepseek_model)
        self.mailer = EmailSender(self.cfg)
        self._seen_dm: set[str] = set()
        self._seen_at: set[int] = set()

    async def start(self):
        await self.db.init()
        log.info("Pluto Bot started ✅")
        await asyncio.gather(
            self._poll_dm_loop(),
            self._poll_at_loop(),
        )

    async def _poll_dm_loop(self):
        while True:
            try:
                await self._check_dms()
            except Exception as e:
                log.error(f"DM poll error: {e}")
            await asyncio.sleep(self.cfg.poll_dm_interval)

    async def _check_dms(self):
        sessions = await self.bili.get_sessions()
        for sess in sessions:
            uid = str(sess.get("talker_id", ""))
            if not uid:
                continue
            msgs = await self.bili.get_session_msgs(int(uid))
            for msg in msgs:
                key = str(msg.get("msg_seqno") or msg.get("msg_key", ""))
                if not key or key in self._seen_dm:
                    continue
                self._seen_dm.add(key)
                if str(msg.get("sender_uid")) == str(self.cfg.bot_uid):
                    continue
                content = msg.get("content", "")
                if isinstance(content, dict):
                    content = content.get("content", "")
                asyncio.create_task(self._handle(uid, str(content)))

    async def _poll_at_loop(self):
        while True:
            try:
                await self._check_mentions()
            except Exception as e:
                log.error(f"AT poll error: {e}")
            await asyncio.sleep(self.cfg.poll_at_interval)

    async def _check_mentions(self):
        items = await self.bili.get_mentions()
        for item in items:
            at_id = item.get("id")
            if not at_id or at_id in self._seen_at:
                continue
            self._seen_at.add(at_id)
            uid = str(item.get("user", {}).get("mid", ""))
            content = item.get("item", {}).get("source_content", "")
            asyncio.create_task(self._handle(uid, str(content)))

    async def _handle(self, uid: str, content: str):
        log.info(f"[{uid}] {content[:80]}")
        uid_int = int(uid)

        email = extract_email(content)
        if email:
            await self.db.save_user_email(uid, email)
            await self.bili.send_message(
                uid_int,
                f"你的邮箱 {email} 已记住啦！📮\n"
                f"下次发给我视频链接或 BV 号，笔记会发到这里~\n"
                f"记得随时呼叫 Pluto Bot 哦！💙",
            )
            return

        bv = extract_bv(content)
        if bv:
            user_email = await self.db.get_user_email(uid)
            if not user_email:
                await self.bili.send_message(
                    uid_int,
                    "收到视频啦！📮\n"
                    "请先发送你的邮箱地址，Pluto Bot 会把笔记发到那里~\n"
                    "例如发送：yourname@gmail.com",
                )
                return

            allowed = await self.db.check_and_increment_usage(uid, self.cfg.daily_limit)
            if not allowed:
                await self.bili.send_message(
                    uid_int,
                    f"今天已经生成了 {self.cfg.daily_limit} 个笔记啦，明天再来哦~ 💙",
                )
                return

            await self.bili.send_message(
                uid_int,
                f"收到啦~ 📮 Pluto Bot 正在为你生成笔记，"
                f"稍后会发送到 {user_email}，请稍等哦！",
            )
            asyncio.create_task(self._process_video(uid_int, bv, user_email))
            return

        await self.bili.send_message(uid_int, HELP_MSG)

    async def _process_video(self, uid: int, bv: str, email: str):
        try:
            meta, subtitle = await self.bili.get_video_info_and_subtitle(bv)
            if not subtitle:
                await self.bili.send_message(
                    uid,
                    f"😅 视频 {bv} 没有找到 CC 字幕，暂时无法生成笔记。\n"
                    "目前支持有字幕的视频，抱歉啦~",
                )
                return

            notes = await self.gen.generate(meta, subtitle)
            subject = f"📚 {meta['title']} | Pluto Bot 笔记"
            ok = await self.mailer.send(email, subject, notes, bv=bv)

            if ok:
                await self.bili.send_message(
                    uid,
                    f"📨 {meta['title']}\n({bv})\n\n"
                    f"已将 Markdown 格式的笔记文件发送至你的邮箱啦~ 📨✨\n"
                    f"记得随时呼叫 Pluto Bot 哦！💙",
                )
            else:
                await self.bili.send_message(uid, "😢 邮件发送失败，请稍后重试。")

        except Exception as e:
            log.error(f"process_video {bv} error: {e}")
            await self.bili.send_message(uid, f"😢 处理 {bv} 时出了问题，请稍后重试。")


if __name__ == "__main__":
    asyncio.run(PlutoBot().start())
