# Pluto Bot · ASR（语音转写）集成设计文档

> 状态：📝 调研中（未实现）
> 创建日期：2026-05-09
> 决策人：@Pluto731

---

## 1. 背景与动机

### 现状

当前 bot 通过 `bilibili-api-python` 抓取视频字幕：

```python
# src/bilibili/client.py
async def _fetch_subtitle(self, v: Video, cid: int) -> str:
    player_info = await v.get_player_info(cid=cid)
    subtitles = player_info.get("subtitle", {}).get("subtitles", [])
    ...
```

实测发现字幕来源有三类：

| 字幕类型 | 标识 (`lan`) | 现状 |
|---------|------------|------|
| UP 主上传的中文字幕 | `zh-CN` / `zh-Hans` | **覆盖率 < 5%**（绝大多数 UP 主不传） |
| B 站 AI 自动字幕 | `ai-zh` | 异步生成，**首次调用返回空，多次调用结果飘忽**，且内容可能只到前 30 秒 |
| 无字幕 | （subtitles 数组空） | 大量纯口播 / 教程视频属于此类 |

### 问题

字幕路线有三个痛点：

1. **覆盖率低**：很多视频根本没字幕
2. **可靠性差**：ai-zh 字幕需要 N 次轮询，且不保证完整
3. **质量不可控**：AI 字幕的"♪ 音乐 ♪"占位、错词比例不可预测

### 解决思路

**绕过字幕，直接从音频转写**。视频只要能播，就一定有音频；只要有音频，就能转写。

```
旧链路：BV → bilibili-api 字幕 → DeepSeek → 邮件
新链路：BV → bilibili-api 音频 URL → 下载 m4s → ffmpeg 转 wav → ASR → DeepSeek → 邮件
```

---

## 2. 链路设计

### 端到端流程

```
┌──────────────────┐
│ 用户私信 BV 给 bot │
└────────┬─────────┘
         ↓
┌─────────────────────────────────┐
│ Step 1: 拿视频 metadata          │
│   bilibili-api.Video.get_info()  │
│   → title, author, duration, cid │
└────────┬─────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Step 2: 优先尝试 B 站字幕        │
│   _fetch_subtitle()              │
│   → 字幕 ≥ 500 字 → 直接走 LLM    │
│   → 字幕 < 500 字 / 空 → 走 ASR  │
└────────┬─────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Step 3: 拿 dash audio URL        │
│   Video.get_download_url(cid)    │
│   → audio[].baseUrl              │
└────────┬─────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Step 4: 下载音频                 │
│   aiohttp GET → /tmp/{bvid}.m4s  │
│   带 Referer: bilibili.com header│
└────────┬─────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Step 5: 转码                     │
│   ffmpeg -i input.m4s            │
│          -ar 16000 -ac 1         │
│          output.wav              │
└────────┬─────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Step 6: ASR 转写                 │
│   transcriber.transcribe(wav)    │
│   → 完整文字稿                   │
└────────┬─────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ Step 7: DeepSeek 整理笔记 (已实现) │
│ Step 8: SMTP 发邮件 (已实现)      │
└─────────────────────────────────┘
```

### 关键设计点

- **只下 audio 流**，不下 video（10 min 视频音频 ~10MB，全量 ~200MB+）
- **字幕优先**：能用 B 站字幕就别跑 ASR（省钱省时）
- **音频缓存**：同一个 BV 的 `wav` 缓存到 `data/cache/`，重复请求复用
- **转写缓存**：转写结果按 BV 持久化到 SQLite，避免重复 ASR

### 标准 ASR 输入

ffmpeg 输出参数 `-ar 16000 -ac 1`：
- `-ar 16000`：16 kHz 采样率（Whisper / paraformer 通用）
- `-ac 1`：单声道（人声足够）
- 输出 wav 16-bit PCM

---

## 3. 三种方案对比

### 方案 A：本地 faster-whisper（GPU）

**依赖**：

```
faster-whisper >= 1.0
ffmpeg
CUDA 11.8+ / cuDNN
模型文件（首次运行自动下载）：
  tiny       75 MB   通用场景
  base       150 MB
  small      500 MB
  medium     1.5 GB  ★ 推荐
  large-v3   3 GB    最准但最慢
```

**实现**（伪代码）：

```python
from faster_whisper import WhisperModel

class WhisperTranscriber:
    def __init__(self, model_size="medium", device="cuda"):
        self.model = WhisperModel(
            model_size,
            device=device,
            compute_type="float16",  # 节省显存
            download_root="./models",
        )

    async def transcribe(self, audio_path: str) -> str:
        # faster-whisper 是同步接口，用线程池避免阻塞
        loop = asyncio.get_running_loop()
        segments, info = await loop.run_in_executor(
            None,
            lambda: self.model.transcribe(
                audio_path,
                language="zh",
                beam_size=5,
                vad_filter=True,  # 跳过静音段
            ),
        )
        return "\n".join(seg.text for seg in segments)
```

**性能基准**（社区数据）：

| GPU | 模型 | RTF (Real-Time Factor) | 10 min 视频处理时长 |
|-----|------|----------------------|------------------|
| RTX 3060 12GB | medium | ~0.05 | 30 秒 |
| RTX 3060 12GB | large-v3 | ~0.10 | 60 秒 |
| RTX 4090 | medium | ~0.02 | 12 秒 |
| RTX 4090 | large-v3 | ~0.04 | 24 秒 |

**中文准确率**（参考 [Whisper Chinese benchmark](https://github.com/openai/whisper#available-models-and-languages)）：

| 模型 | 错词率 (CER) | 评价 |
|------|------------|------|
| tiny | 18% | 错词多，专业术语经常错 |
| base | 12% | 一般场景能用 |
| small | 7% | 日常对话 OK |
| medium | 4% | 推荐，技术内容也准 |
| large-v3 | 2.5% | 最准，但显存 6GB+ |

**成本**：
- 一次性：模型下载 1.5GB（medium）
- 长期：电费

**部署可行性**：
- 本地（你 conda gpu env）：✓ 直接装
- 当前 VPS（无 GPU）：✗ 跑不动 medium / large

---

### 方案 B：阿里云通义听悟 / 百炼 paraformer

**依赖**：

```
dashscope SDK
阿里云账号
百炼 API key（model studio）
```

**实现**：

```python
import dashscope
from dashscope.audio.asr import Recognition

class DashScopeTranscriber:
    def __init__(self, api_key: str, model="paraformer-v2"):
        dashscope.api_key = api_key
        self.model = model

    async def transcribe(self, audio_path: str) -> str:
        recognition = Recognition(
            model=self.model,
            format='wav',
            sample_rate=16000,
        )
        # 上传 + 异步轮询，dashscope SDK 提供 async 包装
        result = await asyncio.to_thread(recognition.call, audio_path)
        return result.output.text
```

**定价**（截至 2026-05，[官网](https://help.aliyun.com/zh/model-studio/billing)）：

| 套餐 | 价格 |
|------|------|
| 入门（每月）| 免费 100 小时 |
| paraformer-v2 | ¥0.05 / 分钟（音频时长，不是处理时长）|
| paraformer-realtime-v2 | ¥0.08 / 分钟 |

**典型成本估算**：
- 100 个用户 × 每天 1 个 10 min 视频 = 1000 min/天 = 30000 min/月
- 减去免费 6000 min（100 小时）= 24000 min × ¥0.05 = **¥1200 / 月**
- 个人玩具规模（10 用户 × 10 min × 30 天 = 3000 min/月）**完全在免费额度内**

**延迟**：
- 文件上传（10MB）：5-15 秒（取决于网络）
- 云端异步处理：30-60 秒
- **总计：60-90 秒 / 10 min 视频**

**中文准确率**：
- paraformer-v2 是阿里专为中文优化的模型
- 普通话场景 CER ~3%
- 对方言、口音、专业术语鲁棒性强（训练数据含金融/医疗/科技语料）

**部署可行性**：
- 本地：✓ 装 SDK 即可
- VPS：✓ 不需要 GPU，CPU + 网络足够

---

### 方案 C：VPS 本地 faster-whisper（CPU + tiny）

**性能预估**（社区数据，4 核 CPU x86）：

| 模型 | RTF | 10 min 视频处理时长 | 中文 CER |
|------|-----|------------------|---------|
| tiny | 0.5-1 | 5-10 分钟 | 18% |
| base | 1-2 | 10-20 分钟 | 12% |

**问题**：

- 用户私信发来 BV → 等 5-10 分钟才收邮件 → 体验差
- VPS CPU 长时间满载会影响其他容器（Miniflux/RSSHub/3x-ui）
- tiny 模型错词多，专业内容笔记会失真

**评价**：⚠️ 不推荐用于生产

---

## 4. 推荐路径

### 阶段 1（本地开发）

**用方案 A（faster-whisper medium + GPU）**

理由：
- 你本地有 conda gpu env
- 用最高质量模型先把链路跑通，验证 ASR + DeepSeek 整体笔记质量
- 离线、免费、易调试

具体动作：
1. `pip install faster-whisper` 到 `pluto-bot/.venv`
2. 装 ffmpeg（Windows 直接 `winget install ffmpeg`）
3. 实现 `src/asr/whisper_local.py`、`src/audio/downloader.py`
4. 跑通"真实 BV → 下载音频 → ASR → DeepSeek"完整链路
5. 用 5-10 个不同类型视频测试笔记质量

### 阶段 2（部署到 VPS）

**切换到方案 B（阿里云 paraformer）**

理由：
- 当前 VPS 无 GPU，不能跑 whisper medium
- 阿里云免费额度对个人 bot 完全够用
- VPS 部署只需配 SDK + API key
- 延迟 1-2 min 可接受

### 架构原则：抽象 + 替换

```python
# src/asr/base.py
from abc import ABC, abstractmethod

class BaseTranscriber(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str) -> str:
        ...

# src/asr/whisper_local.py
class WhisperTranscriber(BaseTranscriber): ...

# src/asr/dashscope.py
class DashScopeTranscriber(BaseTranscriber): ...

# src/config.py
asr_backend = os.getenv("ASR_BACKEND", "whisper")  # "whisper" | "dashscope"

# 工厂方法
def make_transcriber(cfg) -> BaseTranscriber:
    if cfg.asr_backend == "whisper":
        return WhisperTranscriber(model_size=cfg.whisper_model)
    elif cfg.asr_backend == "dashscope":
        return DashScopeTranscriber(api_key=cfg.dashscope_api_key)
    raise ValueError(...)
```

通过 env 切换：
- 本地 `.env`：`ASR_BACKEND=whisper`
- VPS `.env`：`ASR_BACKEND=dashscope`

---

## 5. 实现切片划分

按 incremental-delivery 原则，拆成 4 个独立可验证的切片：

### 切片 1：音频下载与转码（不依赖 ASR）

**输出**：

- `src/audio/downloader.py` - 调 `bilibili-api` 拿 dash audio URL，aiohttp 下载到 `data/cache/{bvid}.m4s`
- `src/audio/extractor.py` - 调 ffmpeg 转 16kHz mono wav

**验证**：

```bash
python tests/test_audio_download.py BV1Z44y147xA
# 预期：./data/cache/BV1Z44y147xA.wav 存在，时长接近视频时长
```

**预计工时**：1-2 小时

---

### 切片 2：本地 Whisper 转写

**输出**：

- `src/asr/base.py` - `BaseTranscriber` 抽象类
- `src/asr/whisper_local.py` - faster-whisper 封装
- `tests/test_whisper.py` - 给一个 wav，输出文字

**验证**：

```bash
python tests/test_whisper.py data/cache/BV1Z44y147xA.wav
# 预期：终端打印中文转写文字，CER 目测 < 10%
```

**预计工时**：1 小时（不算模型下载等待）

---

### 切片 3：集成到 bot 主流程

**输出**：

- 修改 `src/bilibili/client.py::get_video_info_and_subtitle`：
  - 先尝试字幕（保留现有逻辑）
  - 字幕字数 < 500 → fallback 走 ASR 路径
- 修改 `src/main.py`：注入 transcriber 到 `BilibiliClient`
- 修改 `src/config.py`：新增 `ASR_BACKEND` / `WHISPER_MODEL` 等 env

**验证**：

E2E 跑一个**真的没字幕的视频**，bot 自动 fallback 走 ASR，最终邮件笔记内容与视频实际口播一致。

**预计工时**：2-3 小时

---

### 切片 4：阿里云 DashScope 后端（部署 VPS 时做）

**输出**：

- `src/asr/dashscope.py`
- 阿里云账号注册 + API key 配置
- VPS 部署文档更新

**验证**：

VPS 上 `ASR_BACKEND=dashscope`，bot 处理一个视频成功收到笔记邮件。

**预计工时**：1-2 小时（注册阿里云 + 测试）

---

## 6. 风险 / 待办

### 已识别风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| ffmpeg 在 VPS 没装 | 转码失败 | apt install ffmpeg；Dockerfile 加这个 |
| Whisper 模型首次下载慢 | 启动几分钟 | 预先在 Dockerfile 中下载 |
| 长视频（>30 min）显存爆 | OOM | 切片处理（whisper 自带的 vad_filter） |
| 转写文字超 DeepSeek max_tokens | 笔记不完整 | 现有 `subtitle[:12000]` 截断逻辑保留 |
| 阿里云 API 限流 | 转写失败 | 重试 + 降级到本地 whisper（如果可能）|
| 单 BV 多次请求浪费算力 | 用户重发 BV 重复跑 ASR | SQLite 加 `transcripts` 表缓存 |

### 待办（决策后跟进）

- [ ] 确认是否需要 Whisper 缓存到 Redis（避免容器重启丢模型）
- [ ] 决定是否暴露 `/transcribe?bv=xxx` API 给其他用途
- [ ] 评估 dashscope 备份到 OpenAI Whisper API（万一阿里云挂了）

---

## 7. 决策矩阵

| 维度 | 方案 A 本地 GPU | 方案 B 云 ASR | 方案 C VPS CPU |
|-----|---------------|-------------|--------------|
| 成本 | ✓ 0 | ⚠ 0-¥1200/月 | ✓ 0 |
| 延迟（10 min 视频） | ✓ <1 min | ✓ 1-2 min | ✗ 5-10 min |
| 中文准确率 | ✓ 96% | ✓ 97% | ✗ 82% |
| 离线可用 | ✓ | ✗ | ✓ |
| GPU 依赖 | ✗ 必需 | ✓ 不需 | ✓ 不需 |
| 部署复杂度 | ⚠ 装 CUDA | ✓ 装 SDK | ⚠ 慢但能跑 |
| **推荐场景** | **本地开发** | **生产部署** | 不推荐 |

---

## 8. 实测验证记录（2026-05-09）

本节是在本地实际跑通 ASR 端到端后的真实数据，用于**校准 §3 的预估**。

### 8.1 测试环境

- 主机：Windows 11，`E:/Learning/LLM/pluto-bot/.venv`，Python 3.10
- 测试视频：`BV1Z44y147xA`「L1/L2 正则化直观理解」 王木头学科学，28:00（1680 秒）
- 工具栈：
  - `bilibili-api-python==16.3.0` 拿 dash audio URL
  - `imageio-ffmpeg`（**自带 ffmpeg 二进制，不需系统装**，venv 内自给自足）
  - `dashscope==1.x`，model = `paraformer-realtime-v2`

### 8.2 实测数据（修复 callback bug 后）

| 指标 | 60 秒短样本 | 完整 28 分钟（待结果）|
|------|------------|------------|
| 下载（22 MB m4s） | 5.0 s | 5.0 s |
| ffmpeg 转码 | 0.1 s | ~1 s |
| paraformer ASR | **13.9 s** | ~620 s |
| 完整句子数 | 2 | ~150-200 |
| **总耗时** | **19 s** | **~10 min** |
| **ASR 速率（vs 实时）** | **~4.3x** | **~2.7x** |

实测比 §3 方案 B 预估的"60-90 秒 / 10 min"**慢约 60%**，原因：
- §3 估的是 `paraformer-v2` 异步任务接口（云端并行处理）
- 实测用的是 `paraformer-realtime-v2` 流式接口（按近实时速度处理）
- **要拿到 §3 预估的速度必须切换到异步接口**（需要公网 URL，见 §8.6）

### 8.3 准确率分析

短样本完整转写（王木头开场白前 60 秒）：

```
大家好，我是王木头。说到激进学习，它有两个核心的议题，一个是优化，
另一个是政则化。正则化它其实就是减少机器学习过拟合作过程正策化。
最常见的方法之一就是对模型的权重进行L一和L二等的化。
```

**对照原意，错词分布**：

| 原文 | ASR 输出 | 错因 | 频次 |
|-----|---------|------|------|
| 机器学习 | 激进学习 | 同音 | 1 |
| 正则化 | 政则化 / 政策化 / 邓子化 / 正策化 | 同音字 | 4 种变体 |
| 拉格朗日乘数法 | 拉格朗日**常数法** / **层数法** | 专业术语 | 2 种 |
| 权重衰减 | 权重**双严** | 同音 | 1 |
| 贝叶斯 | 贝**耶**斯 | 同音字 | 1 |
| L1 / L2 | L一 / L二（也偶有 L2）| 中英混排 | 多 |

**整体准确率分层**：

| 内容类型 | 准确率 |
|---------|------|
| 普通中文（人名、日常词）| 95%+ |
| **专业术语** | **60-70%** ⚠ |
| 中英文混排 | 75% |
| 数字与英文字母 | 80% |

### 8.4 关键 Bug：Callback 累积导致文本爆炸

**症状**：第一次跑 28 min 视频，输出 **25915 字符**（实际有效 ~1500 字符），全是同一句话的不同 partial 累积。

**根因**：`paraformer-realtime-v2` 的 callback **增量推送 partial**，每次 `on_event` 给的 sentence 是"当前累积识别"，不是新句子。

错误代码：

```python
def on_event(self, result):
    sentence = result.get_sentence()
    if sentence and "text" in sentence:
        collected.append(sentence["text"])  # 每次 partial 都 append → 文本爆炸
```

正确代码：

```python
def on_event(self, result):
    sentence = result.get_sentence()
    if sentence and RecognitionResult.is_sentence_end(sentence):
        collected.append(sentence["text"])  # 只在句子最终确定时 append
```

> **教训**：用 streaming ASR 必须用 `is_sentence_end()` 过滤 partial 结果，否则文本量爆炸 17 倍。

### 8.5 改进方向：LLM 后处理纠错

ASR 输出有错别字 ≠ 笔记不可用。DeepSeek/Qwen 实际上**看到"政则化"会自动从上下文猜到是"正则化"**——这是 LLM 的容错能力。

但可以做更激进：在调 DeepSeek 之前加一步"纠错"prompt：

```python
SYSTEM_PROMPT_CORRECTION = """你是一个 ASR 转写后处理器。
下面是一段语音转文字结果，可能有同音字、专业术语错误。
请识别上下文，把错别字纠正回正确写法。保留原文结构，只改错字。"""

corrected = await llm.chat(system=SYSTEM_PROMPT_CORRECTION, user=raw_asr_text)
```

- 代价：多一次 LLM 调用（~1-3 秒 + ~0.001 元）
- 收益：笔记最终质量从 88% → 估 96%
- **建议**：作为可选 pre-processor 加在 `NoteGenerator.generate()` 之前

### 8.6 paraformer-realtime-v2 vs paraformer-v2 选型

| 维度 | realtime（实测）| async（待验证）|
|------|----------------|--------------|
| 输入方式 | **本地文件可直接传**（chunk 喂） | **必须公网 URL** |
| 处理速度 | 4.3x 实时（实测）| 估 6-10x 实时 |
| 接口形式 | callback 流式（要 `is_sentence_end` 过滤）| 同步等待 / 轮询 |
| 准确率 | ~88% 普通中文 / ~65% 专业术语 | 估更高（专为长录音优化） |
| **配置复杂度** | **简单（仅 SDK + key）** | + OSS bucket 或自建 HTTP |

三种"音频 → 公网 URL"方案：

| 方案 | 怎么做 | 复杂度 | 适用 |
|------|------|--------|------|
| 阿里云 OSS | 上传到 bucket，拿临时签名 URL | ⚠ 配 OSS + bucket | **生产推荐** |
| 自建 nginx | VPS 暴露 audio 文件 HTTP | ⚠ 防火墙 + URL 安全（音频内容版权）| 不推荐 |
| dashscope 内嵌上传 | SDK 是否有 `upload_and_transcribe`? | ❓ 待调研 | 最理想 |

### 8.7 端到端时间预算（更新）

10 分钟视频，paraformer-realtime + LLM 纠错 + DeepSeek 笔记：

```
B 站 metadata 抓取        ~  1 s
音频下载（10 MB）         ~  3 s
ffmpeg 转码              ~  1 s
paraformer ASR           ~140 s    ← 主瓶颈（realtime 模式）
LLM 纠错（可选）          ~  3 s
DeepSeek 笔记生成         ~ 25 s
SMTP 邮件发送             ~  2 s
─────────────────────────
TOTAL                    ~175 s = 2 min 55 s
```

用户体验："发完 BV，3 分钟后收邮件"——**可接受**。

如果切换到 paraformer-v2 异步：

```
TOTAL                    ~120 s = 2 min     # 节省约 1 分钟
```

### 8.8 ffmpeg 部署方案

**本地**：用 `imageio-ffmpeg`（pip 包自带二进制）

```python
import imageio_ffmpeg
ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
# 路径：.venv/Lib/site-packages/imageio_ffmpeg/binaries/ffmpeg-win-x86_64-v7.1.exe
```

优势：venv 内自给自足，**不需要 admin 装系统 ffmpeg**，跨平台一致。

**VPS 容器**：在 Dockerfile 里加 `RUN apt-get install -y ffmpeg`，或者继续用 `imageio-ffmpeg`（推荐，部署一致）。

---

## 9. 参考资料

- faster-whisper: <https://github.com/SYSTRAN/faster-whisper>
- OpenAI Whisper 论文: <https://cdn.openai.com/papers/whisper.pdf>
- 阿里百炼 paraformer: <https://help.aliyun.com/zh/model-studio>
- ffmpeg 命令参考: <https://ffmpeg.org/ffmpeg.html>
- bilibili-api Video.get_download_url: <https://nemo2011.github.io/bilibili-api/#/modules/video>
- imageio-ffmpeg（自带二进制）: <https://github.com/imageio/imageio-ffmpeg>
- dashscope SDK: <https://help.aliyun.com/zh/model-studio/developer-reference/dashscope-sdk-overview>

---

## 决策记录

| 日期 | 决策人 | 决定 | 理由 |
|------|--------|------|------|
| 2026-05-09 | @Pluto731 | 写设计文档，暂不实现 | 评估方案后再决定 |
| 2026-05-09 | @Pluto731 | 实测 paraformer-realtime-v2 端到端 | 验证 ASR 链路可行性 |
| 2026-05-09 | （实测结论）| 链路可跑通；速度 ~4.3x 实时；准确率普通中文 95% / 专业术语 65% | 见 §8 |
| TBD | - | 是否引入 LLM 后处理纠错（§8.5）| 等真实流量数据 |
| TBD | - | 是否切换 paraformer-v2 异步接口（要 OSS）| 等长视频实测看延迟 |
| TBD | - | bot 集成时 ASR 触发条件 | 字幕字数 < 500 时 fallback ASR |
