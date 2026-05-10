"""调试：直接 fetch 字幕 URL"""
import asyncio
import aiohttp


URL = "https://aisubtitle.hdslb.com/bfs/ai_subtitle/prod/11334349907860226390561629b95ec462321d7b06437f91029d828ffa?auth_key=1778293511-4b1135945d3d4af2aa1c6fb1e3c9bea2-0-86a08bf995d70ec3b3509ec3997afc2d"


async def main():
    try:
        async with aiohttp.ClientSession() as sess:
            async with sess.get(URL) as resp:
                print(f"HTTP {resp.status}")
                text = await resp.text()
                print(f"length: {len(text)}")
                print(f"first 400 chars:\n{text[:400]}")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {e}")


asyncio.run(main())
