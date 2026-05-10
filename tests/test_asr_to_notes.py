"""把 paraformer ASR 输出（11293 字符王木头转写）喂给 DeepSeek，
看生成的 markdown 笔记效果。完整链路：ASR文本 → DeepSeek → 邮件 + 本地保存"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from generators.notes import NoteGenerator
from senders.email import EmailSender


REAL_META = {
    "bvid": "BV1Z44y147xA",
    "title": "「L1和L2正则化」直观理解（之一）·从拉格朗日乘数法角度",
    "author": "王木头学科学",
    "duration": "28:00",
    "url": "https://www.bilibili.com/video/BV1Z44y147xA",
}

CACHE = Path(__file__).parent.parent / "data" / "cache"
TRANSCRIPT_PATH = CACHE / "BV1Z44y147xA.transcript.txt"


class FakeCfg:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "Pluto Bot")


async def main():
    transcript = TRANSCRIPT_PATH.read_text(encoding="utf-8")
    print(f"=== 输入 ASR 转写 ===")
    print(f"  长度: {len(transcript)} chars")
    print(f"  preview: {transcript[:200]}...\n")

    print(f"=== Step 1: 调 DeepSeek 生成笔记 ===")
    gen = NoteGenerator(os.environ["DEEPSEEK_API_KEY"], os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"))
    t0 = time.time()
    notes = await gen.generate(REAL_META, transcript)
    elapsed = time.time() - t0
    print(f"  生成完成: {len(notes)} chars in {elapsed:.1f}s\n")

    # 保存到本地，方便看 .md
    notes_path = CACHE / f"{REAL_META['bvid']}.notes.md"
    notes_path.write_text(notes, encoding="utf-8")
    print(f"  本地保存: {notes_path}\n")

    print(f"=== Step 2: 发邮件到 {FakeCfg.smtp_user} ===")
    mailer = EmailSender(FakeCfg)
    subject = f"📚 {REAL_META['title']} | Pluto Bot 真实测试"
    ok = await mailer.send(FakeCfg.smtp_user, subject, notes, bv=REAL_META["bvid"])
    print(f"  邮件: {'OK' if ok else 'FAIL'}")

    print(f"\n=== 笔记预览（前 1500 字符）===")
    print(notes[:1500])
    if len(notes) > 1500:
        print(f"\n... (+{len(notes) - 1500} more chars，完整版见 {notes_path.name} 或邮箱附件)")


if __name__ == "__main__":
    asyncio.run(main())
