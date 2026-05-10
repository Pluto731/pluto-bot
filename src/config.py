import os
from dotenv import load_dotenv
from bilibili_api import Credential

load_dotenv()


class Config:
    def __init__(self):
        self.credential = Credential(
            sessdata=os.environ["BILI_SESSDATA"],
            bili_jct=os.environ["BILI_BILI_JCT"],
            buvid3=os.environ["BILI_BUVID3"],
        )
        self.bot_uid = int(os.environ["BILI_BOT_UID"])
        self.deepseek_api_key = os.environ["DEEPSEEK_API_KEY"]
        self.deepseek_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.qq.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "465"))
        self.smtp_user = os.environ["SMTP_USER"]
        self.smtp_password = os.environ["SMTP_PASSWORD"]
        self.smtp_from_name = os.getenv("SMTP_FROM_NAME", "Pluto Bot")
        self.poll_dm_interval = int(os.getenv("POLL_DM_INTERVAL", "30"))
        self.poll_at_interval = int(os.getenv("POLL_AT_INTERVAL", "60"))
        self.daily_limit = int(os.getenv("DAILY_LIMIT_PER_USER", "10"))
        # ASR 配置
        self.enable_asr_fallback = os.getenv("ENABLE_ASR_FALLBACK", "true").lower() == "true"
        self.subtitle_min_length = int(os.getenv("SUBTITLE_MIN_LENGTH", "500"))
        self.asr_backend = os.getenv("ASR_BACKEND", "dashscope_realtime")
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.dashscope_asr_model = os.getenv("DASHSCOPE_ASR_MODEL", "paraformer-realtime-v2")
