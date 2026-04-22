# Pluto Bot

> A Bilibili bot that generates AI-powered study notes from videos and delivers them via email.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)

## Features

- Monitors Bilibili private messages and @mentions in real-time
- Extracts BV IDs from user messages automatically
- Fetches CC subtitles from Bilibili videos
- Generates structured Markdown study notes using DeepSeek AI
- Delivers notes as `.md` email attachments
- Per-user daily rate limiting
- SQLite-based user email storage

## Architecture

```
User DM / @mention (Bilibili)
         |
   PlutoBot (polls every 30s)
         |
  Bilibili API -> fetch CC subtitle
         |
  DeepSeek API -> generate Markdown notes
         |
  SMTP -> send .md attachment to user's email
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- A Bilibili account (for the bot)
- [DeepSeek API key](https://platform.deepseek.com)
- An email account with SMTP access (QQ Mail recommended)

### 1. Clone the repository

```bash
git clone https://github.com/Pluto731/pluto-bot.git
cd pluto-bot
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your credentials (see [Configuration](#configuration)).

### 3. Get Bilibili Cookies

1. Open [bilibili.com](https://bilibili.com) in your browser and log in with the **bot account**
2. Press `F12` to open DevTools -> **Network** tab
3. Refresh the page, click any request to bilibili.com
4. In **Request Headers**, find the `Cookie` field
5. Extract the values of `SESSDATA`, `bili_jct`, and `buvid3`
6. Find your UID from your space page URL: `space.bilibili.com/YOUR_UID`

### 4. Start the bot

```bash
docker compose up -d
docker logs -f pluto-bot
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BILI_SESSDATA` | yes | — | Bilibili cookie: SESSDATA |
| `BILI_BILI_JCT` | yes | — | Bilibili cookie: bili_jct |
| `BILI_BUVID3` | yes | — | Bilibili cookie: buvid3 |
| `BILI_BOT_UID` | yes | — | Bot account UID |
| `DEEPSEEK_API_KEY` | yes | — | DeepSeek API key |
| `DEEPSEEK_MODEL` | no | `deepseek-chat` | `deepseek-chat` or `deepseek-reasoner` |
| `SMTP_HOST` | no | `smtp.qq.com` | SMTP server host |
| `SMTP_PORT` | no | `465` | SMTP server port |
| `SMTP_USER` | yes | — | SMTP username / email address |
| `SMTP_PASSWORD` | yes | — | SMTP password or app authorization code |
| `SMTP_FROM_NAME` | no | `Pluto Bot` | Sender display name |
| `POLL_DM_INTERVAL` | no | `30` | Private message polling interval (seconds) |
| `POLL_AT_INTERVAL` | no | `60` | @mention polling interval (seconds) |
| `DAILY_LIMIT_PER_USER` | no | `10` | Max notes per user per day |

## User Commands

Users interact with the bot via Bilibili private messages or @mentions:

| Message | Action |
|---------|--------|
| `yourname@email.com` | Register your email address |
| `BV1xxxxxxxxxx` | Generate notes for that video |
| `https://www.bilibili.com/video/BV1xxx` | Generate notes for that video |
| Anything else | Show help message |

**Workflow:**
1. User sends their email to the bot -> bot remembers it
2. User sends a BV number or video link -> bot replies "processing..."
3. Bot fetches CC subtitle -> calls DeepSeek -> generates notes
4. Bot sends `.md` attachment to user's registered email
5. Bot replies with confirmation

## Limitations

- Only works with videos that have **CC subtitles** enabled
- Bilibili may rate-limit API requests if polling is too frequent
- DeepSeek API is a paid service (very affordable)
- Bilibili cookies expire periodically and need to be refreshed

## Operations

```bash
# View logs
docker logs -f pluto-bot

# Restart
docker compose restart

# Update to latest
docker compose pull && docker compose up -d

# Stop
docker compose down
```

## Contributing

PRs and issues are welcome! Please open an issue first to discuss major changes.

## License

MIT (c) [Pluto731](https://github.com/Pluto731)
