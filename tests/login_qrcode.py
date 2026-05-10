"""B 站扫码登录助手：手机扫码 → 拿到 SESSDATA / bili_jct / buvid3"""
import asyncio
import qrcode_terminal
from bilibili_api import login_v2


async def main():
    login = login_v2.QrCodeLogin()
    await login.generate_qrcode()

    print("\n用 B 站【手机 App】扫下面这个二维码：\n")
    qrcode_terminal.draw(login.get_qrcode_url())

    print("\n等待扫码...（扫完后在手机上点确认登录）\n")

    while not login.has_done():
        try:
            event = await login.check_state()
            print(f"  状态：{event.value}")
        except Exception as e:
            print(f"  err: {e}")
        await asyncio.sleep(2)

    cred = login.get_credential()

    print("\n" + "=" * 60)
    print("登录成功！下面三个值复制到 .env：")
    print("=" * 60)
    print(f"BILI_SESSDATA={cred.sessdata}")
    print(f"BILI_BILI_JCT={cred.bili_jct}")
    print(f"BILI_BUVID3={cred.buvid3}")
    print("=" * 60)
    print("\n现在去 https://space.bilibili.com/<你的UID> 看 URL 里的数字")
    print("把它填到 BILI_BOT_UID")


if __name__ == "__main__":
    asyncio.run(main())
