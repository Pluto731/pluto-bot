"""完整链路 E2E 测试（mock B 站抓字幕，其他全真实）

模拟一个完整的用户交互：
  1. 用户已注册邮箱（数据库写入）
  2. 用户给 bot 发了一个 BV
  3. 触发 bot._process_video()
     - 抓字幕：MOCK（绕过 B 站不稳定）
     - 生成笔记：REAL DeepSeek
     - 发邮件：REAL SMTP
     - 回复用户消息：MOCK（验证调用即可）
"""
import asyncio
import logging
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from main import PlutoBot


FAKE_BV = "BV1MOCK000000"
FAKE_META = {
    "bvid": FAKE_BV,
    "title": "PyTorch 张量自动求导原理（10 分钟讲透）- E2E mock",
    "author": "本地测试UP",
    "duration": "10:32",
    "url": f"https://www.bilibili.com/video/{FAKE_BV}",
}
FAKE_SUBTITLE = """大家好，今天我们来讲 PyTorch 的自动求导机制。
autograd 是 PyTorch 的核心，它让我们写神经网络时不用手动算梯度。
首先，我们看张量。每个 tensor 有一个属性叫 requires_grad，默认是 False。
如果你想对它求导，就要把这个属性设为 True，比如 x = torch.tensor([1.0], requires_grad=True)。
然后，所有从 x 开始的运算都会被 autograd 追踪，构建一张计算图。
比如 y = x * 2 + 1，y 会自动有一个 grad_fn 属性，记录这个加法和乘法的节点。
当你调用 y.backward()，PyTorch 会从 y 反向遍历这张图，对每个节点用链式法则算梯度。
最后梯度会累加到 x.grad 里。注意是累加，不是覆盖，所以训练循环里通常要先 zero_grad()。
另一个关键是叶子节点。手动创建的、requires_grad=True 的 tensor 是叶子。
中间结果默认不保留梯度，因为占内存。如果你非要看，可以用 retain_grad()。
最后讲计算图。PyTorch 是动态图，每次 forward 都重建。"""


async def main():
    print("\n=== Step 1: 实例化 PlutoBot ===")
    bot = PlutoBot()
    print(f"  bot_uid = {bot.cfg.bot_uid}")
    print(f"  smtp_user = {bot.cfg.smtp_user}")
    print(f"  daily_limit = {bot.cfg.daily_limit}")

    print("\n=== Step 2: Mock B 站调用 ===")
    bot.bili.get_video_info_and_subtitle = AsyncMock(return_value=(FAKE_META, FAKE_SUBTITLE))
    bot.bili.send_message = AsyncMock(return_value=True)
    print(f"  bili.get_video_info_and_subtitle MOCKED")
    print(f"  bili.send_message MOCKED")

    print("\n=== Step 3: DB 初始化 + 注册测试用户 ===")
    await bot.db.init()
    test_uid = "999000111"
    test_email = bot.cfg.smtp_user
    await bot.db.save_user_email(test_uid, test_email)
    print(f"  user {test_uid} -> email {test_email}")

    print("\n=== Step 4: 调用 _process_video（真实链路 minus B 站）===")
    print(f"  生成笔记会真的调 DeepSeek...")
    print(f"  发邮件会真的发到 {test_email}...\n")

    await bot._process_video(int(test_uid), FAKE_BV, test_email)

    print("\n=== Step 5: 验证 mock 调用 ===")
    bili_calls = bot.bili.get_video_info_and_subtitle.call_count
    msg_calls = bot.bili.send_message.call_count
    print(f"  bili.get_video_info_and_subtitle 被调用 {bili_calls} 次")
    print(f"  bili.send_message 被调用 {msg_calls} 次")

    if bot.bili.send_message.called:
        for i, call in enumerate(bot.bili.send_message.call_args_list, 1):
            uid, text = call[0][0], call[0][1]
            print(f"    回复 {i}: 给 uid={uid}")
            print(f"           内容: {text[:80]!r}...")

    print(f"\n=== DONE ===")
    print(f"  完整流程跑完了。检查 {test_email} 收件箱看 markdown 笔记附件。")


if __name__ == "__main__":
    asyncio.run(main())
