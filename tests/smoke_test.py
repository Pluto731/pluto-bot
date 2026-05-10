"""本地冒烟测试：parser / database / config 三个不需联网/凭证的组件"""
import asyncio
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# ---------- Parser ----------
from bilibili.parser import extract_bv, extract_email

print("=== Parser ===")
cases_bv = [
    # BV 号 = BV + 10 个字符（共 12 字符）
    ("https://www.bilibili.com/video/BV1xx411c7mD", "BV1xx411c7mD"),
    ("看下 BV1xx411c7mD 这个视频", "BV1xx411c7mD"),
    ("bilibili.com/video/BV1xy7ABCDef/?spm_id=xxx", "BV1xy7ABCDef"),
    ("hello world", None),
    ("", None),
    # 边缘 case：BV 号嵌在中文里、首尾带标点
    ("【推荐】BV1xx411c7mD，必看！", "BV1xx411c7mD"),
]
for text, expected in cases_bv:
    got = extract_bv(text)
    assert got == expected, f"extract_bv({text!r}) = {got!r}, expected {expected!r}"
print(f"  OK extract_bv x{len(cases_bv)}")

cases_email = [
    ("我的邮箱 abc@gmail.com 谢谢", "abc@gmail.com"),
    ("user.name+tag@example.co.uk", "user.name+tag@example.co.uk"),
    ("nothing here", None),
    ("@@@@", None),
]
for text, expected in cases_email:
    got = extract_email(text)
    assert got == expected, f"extract_email({text!r}) = {got!r}"
print(f"  OK extract_email x{len(cases_email)}")


# ---------- Database ----------
print("\n=== Database ===")
fd, tmp_db = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DB_PATH"] = tmp_db

# 必须在设置 env 之后再 import
import importlib
import database
importlib.reload(database)
db = database.Database()


async def test_db():
    await db.init()

    await db.save_user_email("12345", "alice@test.com")
    assert await db.get_user_email("12345") == "alice@test.com"
    print("  OK save + get email")

    await db.save_user_email("12345", "alice2@test.com")
    assert await db.get_user_email("12345") == "alice2@test.com"
    print("  OK overwrite email")

    for i in range(3):
        ok = await db.check_and_increment_usage("u1", limit=3)
        assert ok, f"iter {i} should succeed"
    blocked = await db.check_and_increment_usage("u1", limit=3)
    assert not blocked, "limit reached should return False"
    print("  OK 限额 3/3 + 第 4 次拦截")


asyncio.run(test_db())
os.remove(tmp_db)


# ---------- Config ----------
print("\n=== Config ===")
for k in [
    "BILI_SESSDATA", "BILI_BILI_JCT", "BILI_BUVID3", "BILI_BOT_UID",
    "DEEPSEEK_API_KEY", "SMTP_USER", "SMTP_PASSWORD",
]:
    os.environ.pop(k, None)

try:
    from config import Config
    Config()
    print("  FAIL Config() 应当报缺失 env，但没报")
    sys.exit(1)
except KeyError as e:
    print(f"  OK 缺 {e} 时正确报错")

print("\n=== ALL SMOKE TESTS PASSED ===")
