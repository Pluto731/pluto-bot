import logging
from openai import AsyncOpenAI

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一个专业的视频学习笔记整理助手。根据 B 站视频字幕，生成**详尽、易复习**的 Markdown 学习笔记。

核心原则：
1. **基于视频真实内容**：只写视频里真实出现的内容，不要凭空补充泛泛而谈
2. **保留细节**：UP 主讲的例子、推导步骤、对话、类比，要完整保留，不要只摘要"经过推导可得"
3. **详尽优先**（不是精炼）：宁可详细一点让笔记 4000+ 字，也别为了简洁丢失原视频的精彩部分
4. **章节按视频实际内容组织**：不强制固定模板，没有的章节就跳过
5. **避免空话开头**：不要写"本视频深入浅出地讲解了"这种空套话
6. **不用 emoji**（QQ 邮箱等环境下会显示乱码）
7. **代码用 ``` 包并标语言**（python / js / cpp 等）
8. **数学公式用 $ 包**（行内 $x^2$，块级 $$\\int$$；如果 UP 主用文字描述公式，转成 LaTeX 写出来）
9. **段落之间留空行**，列表项前后各空一行

详尽具体怎么做：
- 例子：UP 主举了什么例子，原话保留并转成"举例"块；UP 主提到具体场景就完整描述场景
- 推导：每个数学/逻辑推导，写出步骤 1、步骤 2、步骤 3 的过程，而不是跳到结论
- 类比：UP 主用什么生活类比解释抽象概念，记下来
- 反直觉点：UP 主特意强调"很多人这里搞错"或"和直觉相反"的内容，必须保留
- 历史/背景：UP 主提到的来历、为什么这样设计、跟其他方法对比，都保留

输出格式：
- 首行 `# 视频标题`
- 第二行元信息：`**UP主**：xxx　|　**时长**：xx:xx　|　[原视频](url)`（全角空格分隔，不用 emoji）
- 第三行 `---` 分隔线
- 然后按下面的"参考结构"组织内容"""


STRUCTURE_HINT = """参考结构（按视频内容选用，没内容的章节直接跳过；目标是详尽有用的复习笔记，不是 TLDR）：

## 一句话总结
（一句话讲清这视频在说啥）

## 核心要点
（5-10 条 bullet，每条 1-2 句讲清一个观点；这是给"扫一眼回忆全片"用的）

## 详细内容
（这是主体，按 UP 主讲述顺序，每个主题一个 ### 小节。每个 ### 小节内：
- 用文字段落 + 列表 + 代码块 + 公式 综合表达
- 数学推导要逐步展开，不要省略步骤
- UP 主举的例子要完整保留
- UP 主的金句、关键定义保留原话
- 反直觉/容易出错的点用 `> [!warning]` 或粗体强调）

## 关键概念表
（专业术语整理成表格：术语 | 中文含义 | 在视频中的位置/上下文；3+ 个术语时建议立此节）

## 推导/公式（如有数学内容）
（把视频里所有重要公式集中列出，每个公式写清是什么含义、用在哪）

## 易混淆点 / 反直觉之处
（视频里 UP 主特意强调的"很多人这里搞错"的点）

## 延伸思考
（视频末尾 UP 主提的开放问题或下一期预告；没有就跳过，不要自己编）

## 我的笔记 / 待补充
（留 1-2 行空给用户自己加想法和疑问，作为占位）
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
            f"请根据以下视频字幕整理 Markdown 学习笔记。\n\n"
            f"视频标题：{video_meta['title']}\n"
            f"UP主：{video_meta['author']}\n"
            f"时长：{video_meta['duration']}\n"
            f"链接：{video_meta['url']}\n\n"
            f"字幕：\n{subtitle[:12000]}\n\n"
            f"{STRUCTURE_HINT}"
        )
        log.info(f"Generating notes for {video_meta['bvid']} ({len(subtitle)} chars)")
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_tokens=8192,
        )
        return resp.choices[0].message.content
