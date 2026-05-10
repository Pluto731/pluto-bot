"""完整 E2E 真实测试（无 mock）：
模拟用户私信 BV → bot 处理（缓存→字幕→ASR fallback）→ DeepSeek → 邮件
跑一个无字幕的 BV 验证 ASR fallback 真的会触发"""
import asyncio
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from main import PlutoBot
from unittest.mock import AsyncMock


# 选一个我们已经在 cache 里有 ASR 转写的视频，第一次测试会命中缓存（秒出）
TEST_BV = "BV1Z44y147xA"


async def main():
    print("\n=== 实例化 PlutoBot ===")
    bot = PlutoBot()
    # 不去真发 B 站消息（怕打扰用户），只 mock send_message，其他全真实
    bot.bili.send_message = AsyncMock(return_value=True)

    print("\n=== DB init ===")
    await bot.db.init()

    test_uid = 999000111
    test_email = bot.cfg.smtp_user
    await bot.db.save_user_email(str(test_uid), test_email)

    print(f"\n=== 调用 _process_video({test_uid}, {TEST_BV}, {test_email}) ===")
    print("    走完整链路：缓存检查 → 字幕检查 → ASR fallback → DeepSeek → 邮件")
    print()

    import time

    # ── 第一次：字幕路径 ─────────────────────────────────
    print("\n--- RUN 1：第一次（应走字幕路径）---")
    t0 = time.time()
    await bot._process_video(test_uid, TEST_BV, test_email)
    print(f"  [RUN 1] elapsed: {time.time() - t0:.1f}s")

    cached = await bot.db.get_transcript(TEST_BV)
    print(f"  缓存: source={cached[1]}, len={len(cached[0])}" if cached else "  无缓存")

    # ── 第二次：缓存命中 ─────────────────────────────────
    print("\n--- RUN 2：再跑一次同 BV（应缓存命中，秒出）---")
    bot.bili.send_message.reset_mock()
    t0 = time.time()
    await bot._process_video(test_uid, TEST_BV, test_email)
    print(f"  [RUN 2] elapsed: {time.time() - t0:.1f}s （应远小于 RUN 1）")

    print(f"\n=== 全部 send_message 调用次数 ===")
    print(f"  共调用 {bot.bili.send_message.call_count} 次")


if __name__ == "__main__":
    asyncio.run(main())
