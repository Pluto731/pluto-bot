"""SMTP 邮件发送测试：自己发自己一封带 .md 附件的测试邮件"""
import asyncio
import os
import sys
from pathlib import Path

# 让脚本能 import src/ 下的模块
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from senders.email import EmailSender


class FakeCfg:
    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]
    smtp_from_name = os.environ.get("SMTP_FROM_NAME", "Pluto Bot")


async def main():
    sender = EmailSender(FakeCfg)
    fake_notes = (
        "# 测试笔记 - Pluto Bot 本地冒烟\n\n"
        "## 摘要\n"
        "- 这是一封本地 smoke test 邮件\n"
        "- 验证 SMTP 配置 + 附件发送链路\n\n"
        "## 内容\n"
        "如果你看到这封邮件且能下载到附件 `notes_BVTEST.md`，说明：\n"
        "1. SMTP_SSL 连接 smtp.qq.com:465 OK\n"
        "2. 授权码登录通过\n"
        "3. MIMEMultipart + Base64 附件编码 OK\n"
        "4. UTF-8 中文/Emoji 渲染正常 ✅\n"
    )
    ok = await sender.send(
        to_email=FakeCfg.smtp_user,  # 自己发自己
        subject="📚 Pluto Bot 本地冒烟测试 | Milky 的小白鼠",
        notes_md=fake_notes,
        bv="BVTEST",
    )
    if ok:
        print(f"\n[OK] sent to {FakeCfg.smtp_user}")
        print("     check QQ inbox (or spam)")
    else:
        print("\n[FAIL] see log above")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
