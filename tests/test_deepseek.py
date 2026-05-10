"""DeepSeek API 测试：用 fake meta + 短字幕生成笔记，验证 base_url/api_key/模型调用都通"""
import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from generators.notes import NoteGenerator


FAKE_META = {
    "bvid": "BVTEST",
    "title": "PyTorch 张量自动求导原理（10 分钟讲透）",
    "author": "知识区UP主",
    "duration": "10:32",
    "url": "https://www.bilibili.com/video/BVTEST",
}

# 一段稍微像样的"伪字幕"——让 DeepSeek 真有内容可总结
FAKE_SUBTITLE = """
大家好，今天我们来讲 PyTorch 的自动求导机制。
autograd 是 PyTorch 的核心，它让我们写神经网络时不用手动算梯度。
首先，我们看张量。每个 tensor 有一个属性叫 requires_grad，默认是 False。
如果你想对它求导，就要把这个属性设为 True，比如 x = torch.tensor([1.0], requires_grad=True)。
然后，所有从 x 开始的运算都会被 autograd 追踪，构建一张计算图。
比如 y = x * 2 + 1，y 会自动有一个 grad_fn 属性，记录这个加法和乘法的节点。
当你调用 y.backward()，PyTorch 会从 y 反向遍历这张图，对每个节点用链式法则算梯度。
最后梯度会累加到 x.grad 里。注意是累加，不是覆盖，所以训练循环里通常要先 zero_grad()。
另一个关键是叶子节点。手动创建的、requires_grad=True 的 tensor 是叶子。
中间结果默认不保留梯度，因为占内存。如果你非要看，可以用 retain_grad()。
最后讲计算图。PyTorch 是动态图，每次 forward 都重建。这跟 TensorFlow 1.x 的静态图不一样，
好处是写法灵活，调试方便；缺点是没法做太极致的图优化。但够用了，研究阶段灵活最重要。
今天就讲到这里，下一期我们讲 nn.Module 怎么把 autograd 包装起来。
""".strip()


async def main():
    api_key = os.environ["DEEPSEEK_API_KEY"]
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    print(f"[INFO] model = {model}, key = {api_key[:8]}...{api_key[-4:]}")

    gen = NoteGenerator(api_key, model)

    t0 = time.time()
    notes = await gen.generate(FAKE_META, FAKE_SUBTITLE)
    elapsed = time.time() - t0

    print(f"\n[OK] generated in {elapsed:.1f}s, {len(notes)} chars")
    print("=" * 70)
    print(notes)
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
