# 🤖 LinkedIn AI Agent

> An autonomous, production-ready AI agent that generates, reviews, and publishes LinkedIn posts — built with Python 3.12+, FastAPI, and OpenAI.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🚀 Quick Start

```bash
# 1. Clone and setup
cd linkedin-agent
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. Configure
copy .env.example .env
# Edit .env with your API keys

# 3. Run
uvicorn app.main:app --reload

# 4. Open Swagger UI
# http://localhost:8000/docs
```

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **AI Content Generation** | GPT-4o & Gemini — professional hooks, body, CTA, hashtags |
| 🖼️ **Smart Images** | Unsplash, Pexels, Pixabay, DALL-E 3 with auto-fallback |
| 🔗 **Relevant Links** | Auto-searches for high-quality sources |
| 👁️ **Human Review** | Full preview before any publishing — never auto-posts |
| ✏️ **Rich Editing** | Edit any field: hook, body, CTA, hashtags, image, links |
| 🔄 **Regeneration** | Regenerate any part without starting over |
| ⏰ **Daily Scheduler** | APScheduler cron at configurable time |
| 🧠 **Memory** | Tracks topics, avoids duplicates, learns preferences |
| 📊 **Analytics** | Dashboard with views, likes, engagement rate |
| 🔐 **LinkedIn OAuth2** | Full OAuth2 flow for secure publishing |

---

## 📁 Project Structure

```
linkedin-agent/
├── app/
│   ├── main.py              ← FastAPI app entry point
│   ├── config.py            ← Pydantic Settings (all env vars)
│   ├── api/
│   │   ├── router.py        ← Aggregates all routes
│   │   └── endpoints/
│   │       ├── generate.py  ← POST /generate
│   │       ├── preview.py   ← GET/POST /preview
│   │       ├── publish.py   ← POST /publish
│   │       ├── edit.py      ← POST /edit
│   │       ├── regenerate.py← POST /regenerate
│   │       ├── schedule.py  ← GET/POST /schedule
│   │       ├── history.py   ← GET /history
│   │       ├── analytics.py ← GET /analytics
│   │       └── settings.py  ← GET/PUT /settings
│   ├── agents/
│   │   ├── content_agent.py ← Orchestrates full generation pipeline
│   │   ├── review_agent.py  ← Manages review state machine
│   │   └── memory_agent.py  ← Memory read/write coordination
│   ├── services/
│   │   ├── ai_service.py    ← OpenAI + Gemini generation
│   │   ├── image_service.py ← Unsplash/Pexels/Pixabay/DALL-E
│   │   ├── link_service.py  ← Link search (DuckDuckGo + curated)
│   │   ├── linkedin_service.py ← LinkedIn OAuth2 + Publishing
│   │   └── scheduler_service.py ← APScheduler management
│   ├── database/
│   │   ├── base.py          ← Engine + session + get_db
│   │   ├── models.py        ← All ORM models
│   │   ├── crud.py          ← All CRUD operations
│   │   └── init_db.py       ← DB initialization
│   ├── models/
│   │   └── schemas.py       ← All Pydantic schemas
│   ├── prompts/
│   │   ├── post_prompt.py   ← LinkedIn post generation prompts
│   │   ├── hashtag_prompt.py← Hashtag generation prompts
│   │   └── image_prompt.py  ← Image search/DALL-E prompts
│   ├── memory/
│   │   └── memory_store.py  ← JSON + DB hybrid memory
│   ├── scheduler/
│   │   └── jobs.py          ← Daily job function
│   ├── templates/
│   │   └── preview.html     ← Jinja2 post preview template
│   └── utils/
│       ├── logger.py        ← Loguru structured logging
│       ├── helpers.py       ← General utilities
│       └── rate_limiter.py  ← SlowAPI rate limiter
├── tests/
│   ├── conftest.py          ← Fixtures + test DB
│   ├── test_ai_service.py   ← AI service unit tests
│   ├── test_content_agent.py← Content agent unit tests
│   └── test_api_endpoints.py← API integration tests
├── docs/
├── data/                    ← Auto-created: memory.json
├── logs/                    ← Auto-created: agent.log
├── .env.example
├── requirements.txt
├── README.md
├── builder_agent_playbook.md
└── getting_started.md
```

---

## 🔄 Core Workflow

```
1. POST /api/v1/generate          → AI creates draft (PENDING_REVIEW)
         ↓
2. GET  /api/v1/preview/{id}      → You review the full post
         ↓
3. POST /api/v1/edit              → (Optional) Edit any field
         ↓
4. POST /api/v1/preview/{id}/approve → Mark as APPROVED
         ↓
5. POST /api/v1/publish           → Publish to LinkedIn ✅
```

> ⚠️ **Safety**: Publishing requires `status=approved` AND `confirm=true`. There is no way to bypass this.

---

## 🌐 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/generate` | Generate a new post draft |
| `GET` | `/api/v1/preview/{id}` | Get post preview |
| `POST` | `/api/v1/preview/{id}/approve` | Approve for publishing |
| `POST` | `/api/v1/preview/{id}/cancel` | Cancel a draft |
| `POST` | `/api/v1/publish` | Publish approved post |
| `POST` | `/api/v1/edit` | Edit a draft field |
| `POST` | `/api/v1/edit/bulk` | Edit multiple fields |
| `POST` | `/api/v1/regenerate` | Regenerate parts |
| `GET` | `/api/v1/schedule` | Get scheduler status |
| `POST` | `/api/v1/schedule` | Update schedule |
| `POST` | `/api/v1/schedule/trigger` | Trigger now |
| `GET` | `/api/v1/history` | Post history |
| `GET` | `/api/v1/history/pending` | Pending approvals |
| `GET` | `/api/v1/analytics` | Dashboard data |
| `GET` | `/api/v1/settings` | Current settings |
| `PUT` | `/api/v1/settings` | Update settings |
| `GET` | `/auth/linkedin` | Get OAuth2 URL |
| `GET` | `/health` | Health check |

---

## 🔑 Required API Keys

| Service | Key | Free Tier | Get It |
|---|---|---|---|
| OpenAI | `OPENAI_API_KEY` | No (pay per use) | [platform.openai.com](https://platform.openai.com) |
| Gemini | `GEMINI_API_KEY` | Yes | [aistudio.google.com](https://aistudio.google.com) |
| Unsplash | `UNSPLASH_API_KEY` | Yes (50/hr) | [unsplash.com/developers](https://unsplash.com/developers) |
| Pexels | `PEXELS_API_KEY` | Yes | [pexels.com/api](https://www.pexels.com/api/) |
| Pixabay | `PIXABAY_API_KEY` | Yes | [pixabay.com/api/docs](https://pixabay.com/api/docs/) |
| LinkedIn | `LINKEDIN_*` | Yes | [linkedin.com/developers](https://www.linkedin.com/developers/apps) |

---

## 🧪 Running Tests

```bash
pytest tests/ -v --tb=short
pytest tests/ -v --cov=app --cov-report=html
```

---

## 📝 License

MIT License — see [LICENSE](LICENSE)
