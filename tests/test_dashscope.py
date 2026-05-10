"""阿里百炼 API 测试：
  Test 1: Qwen LLM (qwen-plus) 验证 key 能用
  Test 2: Paraformer ASR 用官方样例音频做转写"""
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import dashscope
from dashscope import Generation
from dashscope.audio.asr import Transcription

dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]
key = dashscope.api_key
print(f"[INFO] dashscope key: {key[:8]}...{key[-4:]}")


# ─── Test 1: Qwen LLM ─────────────────────────────────
print("\n=== Test 1: Qwen-Plus LLM ===")
t0 = time.time()
resp = Generation.call(
    model="qwen-plus",
    messages=[
        {"role": "system", "content": "你是一个简洁的助手。回答不超过 50 字。"},
        {"role": "user", "content": "用一句话讲清 PyTorch autograd 是什么"},
    ],
    result_format="message",
)
elapsed = time.time() - t0

if resp.status_code == 200:
    text = resp.output.choices[0].message.content
    print(f"  [OK] {elapsed:.1f}s, {len(text)} chars")
    print(f"  reply: {text}")
else:
    print(f"  [FAIL] code={resp.code}, msg={resp.message}")
    sys.exit(1)


# ─── Test 2: Paraformer ASR (sample audio) ────────────
print("\n=== Test 2: Paraformer-v2 ASR ===")
SAMPLE_URL = (
    "https://dashscope.oss-cn-beijing.aliyuncs.com/samples/audio/paraformer/hello_world_female2.wav"
)
print(f"  sample audio: {SAMPLE_URL}")

t0 = time.time()
task_resp = Transcription.async_call(
    model="paraformer-v2",
    file_urls=[SAMPLE_URL],
    language_hints=["zh"],
)
print(f"  task_id: {task_resp.output.task_id}")
print(f"  status: {task_resp.output.task_status}")

# 阻塞等待完成
result = Transcription.wait(task=task_resp.output.task_id)
elapsed = time.time() - t0

if result.status_code != 200:
    print(f"  [FAIL] {result.code}: {result.message}")
    sys.exit(1)

print(f"\n  [OK] task done in {elapsed:.1f}s")

# 解析结果（每个 file 对应一个 transcription_url，里面是 JSON）
import httpx
for entry in result.output["results"]:
    url = entry.get("transcription_url")
    if not url:
        print(f"  [WARN] no transcription_url: {entry}")
        continue
    print(f"  transcription_url: {url[:80]}...")

    r = httpx.get(url, timeout=15)
    transcript = r.json()
    text_pieces = []
    for sentence in transcript.get("transcripts", [{}])[0].get("sentences", []):
        text_pieces.append(sentence.get("text", ""))
    full_text = "\n".join(text_pieces)
    print(f"  转写文本（{len(full_text)} chars）：")
    print(f"  ---")
    print(full_text)
    print(f"  ---")
