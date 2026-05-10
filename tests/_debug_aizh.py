"""调试 ai-zh 字幕的稳定性 / 激活机制"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from bilibili_api import Credential
from bilibili_api.video import Video

BVID = "BV1Z44y147xA"


async def main():
    cred = Credential(
        sessdata=os.environ["BILI_SESSDATA"],
        bili_jct=os.environ["BILI_BILI_JCT"],
        buvid3=os.environ["BILI_BUVID3"],
    )

    # 三次调用 get_player_info 看是否一致
    for i in range(3):
        v = Video(bvid=BVID, credential=cred)
        info = await v.get_info()
        cid = info["pages"][0]["cid"]
        player = await v.get_player_info(cid=cid)
        subs = player.get("subtitle", {}).get("subtitles", [])
        print(f"[try {i+1}] subtitles count: {len(subs)}, langs: {[s.get('lan') for s in subs]}")
        if subs:
            print(f"   url: {subs[0].get('subtitle_url', '')[:80]}...")
        await asyncio.sleep(1)


asyncio.run(main())
