"""扫几个候选 BV 找一个有官方/UP 字幕的视频，用作 deepseek 测试输入"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from bilibili_api import Credential
from bilibili_api.video import Video

CANDIDATES = [
    "BV1Mb411e7m5",   # 李沐 - 03 安装
    "BV1bb411B7C9",   # 李沐 - 04 数据操作
    "BV1Q5411f7vg",   # 李沐 - 05 数据预处理
    "BV1J54y187f9",   # 李沐 - 06 矩阵计算
    "BV1Z44y147xA",   # 李沐 - 08 线性回归
    "BV1tV4y1H7k4",   # 3Blue1Brown 中文 - 神经网络
    "BV1Wq4y1J7Bk",   # 李沐 - 论文精读
    "BV1ix411D78j",   # 知名科普
]


async def main():
    cred = Credential(
        sessdata=os.environ["BILI_SESSDATA"],
        bili_jct=os.environ["BILI_BILI_JCT"],
        buvid3=os.environ["BILI_BUVID3"],
    )
    found = []
    for bv in CANDIDATES:
        try:
            v = Video(bvid=bv, credential=cred)
            info = await v.get_info()
            cid = info["pages"][0]["cid"]
            player = await v.get_player_info(cid=cid)
            subs = player.get("subtitle", {}).get("subtitles", [])
            title = info["title"][:40]
            print(f"  {bv}: title={title!r:42s}  subs={len(subs)}")
            if subs:
                lans = [s.get("lan") for s in subs]
                print(f"    -> langs: {lans}")
                found.append((bv, title))
        except Exception as e:
            print(f"  {bv}: ERROR {e}")

    print(f"\n=== Summary ===")
    print(f"  Found {len(found)} videos with subtitles:")
    for bv, t in found:
        print(f"    {bv}  {t}")


asyncio.run(main())
