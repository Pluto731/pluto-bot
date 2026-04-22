import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

log = logging.getLogger(__name__)


class EmailSender:
    def __init__(self, cfg):
        self.host = cfg.smtp_host
        self.port = cfg.smtp_port
        self.user = cfg.smtp_user
        self.password = cfg.smtp_password
        self.from_name = cfg.smtp_from_name

    async def send(self, to_email: str, subject: str, notes_md: str, bv: str = "") -> bool:
        try:
            msg = MIMEMultipart()
            msg["From"] = f"{self.from_name} <{self.user}>"
            msg["To"] = to_email
            msg["Subject"] = subject

            body = (
                f"你好！\n\n"
                f"Pluto Bot 为你整理了视频笔记，详见附件 📎\n\n"
                f"视频：https://www.bilibili.com/video/{bv}\n\n"
                f"记得随时呼叫 Pluto Bot 哦！💙\n"
            )
            msg.attach(MIMEText(body, "plain", "utf-8"))

            attachment = MIMEBase("application", "octet-stream")
            attachment.set_payload(notes_md.encode("utf-8"))
            encoders.encode_base64(attachment)
            filename = f"notes_{bv}.md" if bv else "notes.md"
            attachment.add_header("Content-Disposition", f'attachment; filename="{filename}"')
            msg.attach(attachment)

            with smtplib.SMTP_SSL(self.host, self.port) as server:
                server.login(self.user, self.password)
                server.sendmail(self.user, to_email, msg.as_string())

            log.info(f"Email sent to {to_email} for {bv}")
            return True
        except Exception as e:
            log.error(f"Email send failed to {to_email}: {e}")
            return False
