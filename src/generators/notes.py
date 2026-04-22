import logging
from openai import AsyncOpenAI

log = logging.getLogger(__name__)

SYSTEM_PROMPT = "你是一个专业的 B 站视频学习笔记助手，根据提供的视频字幕，生成结构清晰、内容精炼的 Markdown 学习笔记，方便以后复习查阅。"

NOTE_TEMPLATE = """# {title}

> 📺 UP主：{author} | 时长：{duration} | [原视频]({url})

## 📝 视频摘要

## 🔑 核心要点

## 📊 详细笔记

## 💡 关键结论

## ❓ 延伸思考

---
*由 Pluto Bot 自动生成 · {url}*
"""


class NoteGenerator:
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )
        self.model = model

    async def generate(self, video_meta: dict, subtitle: str) -> str:
        user_prompt = (
            f"请根据以下视频字幕生成完整的 Markdown 学习笔记。\n\n"
            f"视频标题：{video_meta['title']}\n"
            f"UP主：{video_meta['author']}\n"
            f"时长：{video_meta['duration']}\n"
            f"链接：{video_meta['url']}\n\n"
            f"字幕内容：\n{subtitle[:12000]}\n\n"
            f"笔记结构参考：\n{NOTE_TEMPLATE.format(**video_meta)}"
        )
        log.info(f"Generating notes for {video_meta['bvid']} ({len(subtitle)} chars)")
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=4096,
        )
        return resp.choices[0].message.content
