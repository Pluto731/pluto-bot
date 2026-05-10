"""B 站 client 测试：用真实 cookie 抓一个有 CC 字幕的视频
测试视频：李沐《动手学深度学习》课程（B 站知名有官方 CC 字幕的视频）"""
import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from bilibili_api import Credential
from bilibili.client import BilibiliClient


# 已知有 CC 字幕的视频（李沐 - 1.1 课程介绍）
TEST_BVID = "BV1Z44y147xA"  # L1/L2 正则化讲解，有 ai-zh 字幕


async def main():
    cred = Credential(
        sessdata=os.environ["BILI_SESSDATA"],
        bili_jct=os.environ["BILI_BILI_JCT"],
        buvid3=os.environ["BILI_BUVID3"],
    )
    bot_uid = int(os.environ["BILI_BOT_UID"])
    print(f"[INFO] bot_uid = {bot_uid}")

    cli = BilibiliClient(cred, bot_uid)

    print(f"\n[1/3] 抓视频元信息 + 字幕：{TEST_BVID}")
    meta, subtitle = await cli.get_video_info_and_subtitle(TEST_BVID)
    print(f"  title    : {meta['title']}")
    print(f"  author   : {meta['author']}")
    print(f"  duration : {meta['duration']}")
    print(f"  url      : {meta['url']}")
    print(f"  subtitle : {len(subtitle)} chars")
    if subtitle:
        print(f"  preview  : {subtitle[:120]}...")
    else:
        print("  [WARN] no subtitle for this video, try another BV")

    print(f"\n[2/3] 拉未读私信会话")
    sessions = await cli.get_sessions()
    print(f"  unread sessions: {len(sessions)}")

    print(f"\n[3/3] 拉 @ 提及")
    mentions = await cli.get_mentions()
    print(f"  mentions: {len(mentions)}")

    print("\n[OK] all bilibili API calls succeeded")
    print("     subtitle long enough to feed deepseek?", len(subtitle) > 300)


if __name__ == "__main__":
    asyncio.run(main())
