# 🏗️ Builder Agent Playbook

> Complete architecture, coding standards, deployment guide, and best practices for the LinkedIn AI Agent.

---

## 1. Project Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        User / Client                         │
└────────────────────────┬────────────────────────────────────┘
                         │ HTTP REST
┌────────────────────────▼────────────────────────────────────┐
│                    FastAPI (app/main.py)                      │
│  CORS │ Rate Limiting │ Logging │ OAuth2 │ Swagger UI        │
└──────┬──────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                    API Router (app/api/)                      │
│  /generate │ /preview │ /publish │ /edit │ /regenerate      │
│  /schedule │ /history │ /analytics │ /settings              │
└──────┬──────────────────────────────────────────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│                    Agent Layer (app/agents/)                  │
│   ContentAgent │ ReviewAgent │ MemoryAgent                   │
└──────┬───────────────────────┬───────────────────────────────┘
       │                       │
┌──────▼──────────┐   ┌────────▼────────────────────────────┐
│  Services Layer  │   │         Memory Layer                  │
│  ai_service.py  │   │  memory_store.py (JSON + DB hybrid)  │
│  image_service  │   └──────────────────────────────────────┘
│  link_service   │
│  linkedin_svc   │   ┌─────────────────────────────────────┐
│  scheduler_svc  │   │       Database Layer (SQLite)         │
└─────────────────┘   │  User │ Draft │ Post │ Analytics     │
                       │  History │ Settings │ SchedulerJob  │
                       └─────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Files | Responsibility |
|---|---|---|
| **API** | `app/api/` | HTTP routing, request validation, response serialization |
| **Agents** | `app/agents/` | Business logic orchestration |
| **Services** | `app/services/` | External API integration (AI, images, LinkedIn) |
| **Database** | `app/database/` | ORM models, CRUD operations, migrations |
| **Memory** | `app/memory/` | Persistent agent state across sessions |
| **Prompts** | `app/prompts/` | AI prompt engineering templates |
| **Utils** | `app/utils/` | Shared utilities (logging, helpers, rate limiting) |
| **Scheduler** | `app/scheduler/` | APScheduler job definitions |

---

## 2. Development Roadmap

### Phase 1 (Current) — Foundation ✅
- [x] FastAPI REST API with all endpoints
- [x] SQLite database with SQLAlchemy ORM
- [x] OpenAI + Gemini AI integration
- [x] Multi-provider image service
- [x] LinkedIn OAuth2 + publishing
- [x] APScheduler daily job
- [x] Human-in-the-loop review workflow
- [x] Memory store (JSON + DB)
- [x] Comprehensive logging
- [x] Unit + integration tests

### Phase 2 — Enhancement
- [ ] Web UI dashboard (React/Next.js)
- [ ] Email/Slack notifications for pending reviews
- [ ] LinkedIn analytics auto-refresh (cron)
- [ ] Multi-user support with authentication
- [ ] PostgreSQL migration with Alembic
- [ ] Post performance A/B testing

### Phase 3 — Advanced
- [ ] Fine-tuned model for personalized style
- [ ] Competitor post analysis
- [ ] Optimal posting time prediction
- [ ] LinkedIn carousel/document posts
- [ ] Auto-response to comments (with approval)
- [ ] Multi-platform support (Twitter/X, Medium)

---

## 3. Coding Standards

### Python Style
- **Python version**: 3.12+
- **Type hints**: Required on all functions and methods
- **Docstrings**: Google-style docstrings on all public functions
- **Line length**: 100 characters max
- **Formatter**: `black`
- **Linter**: `ruff`
- **Type checker**: `mypy`

### File Organization Rules
```python
# Order of imports (enforced by ruff)
from __future__ import annotations  # Always first

import stdlib_module                  # 1. Standard library
from stdlib_module import something

import third_party_module             # 2. Third-party
from third_party import something

from app.local import something       # 3. Local app imports
```

### Naming Conventions
| Type | Convention | Example |
|---|---|---|
| Module | `snake_case` | `ai_service.py` |
| Class | `PascalCase` | `ContentAgent` |
| Function | `snake_case` | `generate_post()` |
| Constants | `UPPER_SNAKE` | `DAILY_JOB_ID` |
| Routes | `kebab-case` | `/api/v1/post-history` |
| DB Tables | `snake_case plural` | `post_history` |

### Error Handling Pattern
```python
# Always use specific exception types
try:
    result = await ai_service.generate_post(topic)
except AIServiceError as e:
    log.error(f"AI generation failed: {e}")
    raise HTTPException(status_code=503, detail=str(e))
except Exception as e:
    log.error(f"Unexpected error: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="Internal error")
```

---

## 4. Folder Explanations

### `app/agents/` — Business Logic
Agents are high-level orchestrators. They:
- Coordinate between multiple services
- Implement business rules (e.g., no auto-publish)
- Manage state transitions
- Should NOT directly make HTTP calls (that's services)

### `app/services/` — External Integrations
Services are thin wrappers around external APIs. They:
- Handle authentication
- Make HTTP calls
- Handle retries and errors
- Return typed result objects
- Should NOT contain business logic

### `app/database/` — Data Layer
- `models.py`: ORM definitions only
- `crud.py`: All DB operations (no business logic)
- `base.py`: Engine and session factory
- Follow repository pattern — no raw SQL in agents

### `app/prompts/` — Prompt Engineering
- Keep prompts versioned and testable
- Use structured output (JSON) for all AI responses
- Include examples in few-shot prompts
- Document expected output format

---

## 5. API Design

### REST Conventions
- `GET` for reads, `POST` for mutations
- Use appropriate HTTP status codes:
  - `200 OK` — successful read
  - `201 Created` — successful create
  - `400 Bad Request` — validation error
  - `404 Not Found` — resource not found
  - `422 Unprocessable Entity` — Pydantic validation error
  - `503 Service Unavailable` — external API failure

### Response Shape
All responses use consistent shapes:
```json
// Success
{"success": true, "message": "...", "data": {...}}

// Error
{"success": false, "error": "...", "detail": "..."}
```

### Versioning
All routes are prefixed with `/api/v1`. When breaking changes are needed, create `/api/v2` routes without removing v1.

---

## 6. Agent Workflow

### Content Generation Pipeline
```
generate_post(topic?)
    │
    ├─ 1. select_topic()          ← MemoryStore + DB (avoid recent)
    │
    ├─ 2. get_context()           ← Memory (style, hashtags, angles)
    │
    ├─ 3. ai.generate_post()      ← OpenAI/Gemini API call
    │                               ↓ Parse JSON response
    │                               ↓ Validate output
    │
    ├─ 4. duplicate_check()       ← Hash comparison in memory + DB
    │
    ├─ 5. clean_hashtags()        ← Normalize format
    │
    ├─ 6. image_service.fetch()   ← Try providers in priority order
    │
    ├─ 7. link_service.find()     ← DuckDuckGo + curated fallback
    │
    ├─ 8. crud.create_draft()     ← Save to SQLite
    │
    └─ 9. memory.record()         ← Update JSON memory store
```

### Review State Machine
```
DRAFT
  │
  ▼
PENDING_REVIEW ←──────── editing returns here
  │                              ↑
  ├──── approve() ──────────────────────────────────
  │         ▼
  │      APPROVED
  │         │
  │         ├──── publish() ──→ PUBLISHED ✅
  │         │
  │         └──── cancel() ──→ CANCELLED
  │
  └──── cancel() ──────────────────────────────────→ CANCELLED
```

---

## 7. Prompt Engineering

### Design Principles
1. **Structured Output**: Always request JSON responses for reliable parsing
2. **Context Injection**: Include recent topics, style preferences, and avoid-list
3. **Constraints First**: Define length, format, and content rules at the top
4. **Examples**: Include 1-2 examples for complex prompts
5. **Fallbacks**: Always have fallback logic if AI returns invalid JSON

### Post Generation Prompt Architecture
```
System Prompt (role + persona + quality standards)
  +
User Prompt (topic + style + constraints + avoid-list + output format)
  =
JSON Response {hook, body, cta, full_post, hashtags, topic_angle}
```

### Prompt Versioning
When updating prompts:
1. Bump version in `prompts/post_prompt.py`
2. Test on 10+ topics before deploying
3. Keep old version as comment for rollback reference

---

## 8. Error Handling

### Error Categories

| Category | HTTP Code | Action |
|---|---|---|
| Validation Error | 422 | Return Pydantic error details |
| Not Found | 404 | Return human-readable message |
| AI API Error | 503 | Try fallback provider, then fail gracefully |
| LinkedIn Error | 503 | Return specific LinkedIn error |
| Rate Limited | 429 | Return retry-after header |
| Unexpected | 500 | Log full traceback, return generic message |

### Retry Strategy (Tenacity)
```python
@retry(
    stop=stop_after_attempt(3),        # Max 3 attempts
    wait=wait_exponential(min=2, max=10),  # Exponential backoff
    retry=retry_if_exception_type(httpx.RequestError),
    reraise=True,
)
async def api_call():
    ...
```

---

## 9. Deployment Guide

### Docker (Recommended)
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production
```bash
APP_ENV=production
DEBUG=false
DATABASE_URL=postgresql://user:pass@db:5432/linkedin_agent
SECRET_KEY=<generated-strong-secret>
LOG_LEVEL=WARNING
```

### PostgreSQL Migration
1. Update `DATABASE_URL` in `.env`
2. Install `psycopg2-binary`: `pip install psycopg2-binary`
3. Run: `python -c "from app.database.init_db import init_db; init_db()"`

---

## 10. Future Improvements

- **Streaming responses**: Stream AI generation for faster perceived performance
- **Redis caching**: Cache AI responses for identical prompts
- **Celery workers**: Move AI generation to background tasks
- **WebSockets**: Real-time generation status updates
- **Fine-tuning**: Fine-tune GPT-3.5 on your best-performing posts
- **A/B testing**: Generate 2 versions, pick the better one
- **LinkedIn Analytics API**: Full integration with impression/click data

---

## 11. Testing Strategy

### Unit Tests
- Mock all external APIs (OpenAI, LinkedIn, Unsplash)
- Test each service in isolation
- Use `pytest-asyncio` for async functions
- Aim for 80%+ coverage on business logic

### Integration Tests
- Use TestClient with in-memory SQLite
- Test complete request/response cycles
- Test error conditions explicitly
- Verify review workflow state transitions

### Test Data
- Use `conftest.py` fixtures for reusable test data
- Never use production data in tests
- Clean up test DB after each test session

---

## 12. Security Checklist

- ✅ All secrets in environment variables (never hardcoded)
- ✅ Input validation with Pydantic on all endpoints
- ✅ Rate limiting on all mutation endpoints
- ✅ SQL injection prevented by SQLAlchemy ORM
- ✅ No sensitive data in logs (`diagnose=False` in file handler)
- ✅ CORS configured to specific origins
- ✅ LinkedIn token stored securely (not in logs)
- ✅ `confirm=true` required for destructive publish action
- ⬜ HTTPS enforcement (configure at reverse proxy/nginx level)
- ⬜ API key authentication for multi-user deployment
- ⬜ Input sanitization for HTML template rendering
- ⬜ Rotate LinkedIn access tokens automatically

---

## 13. Best Practices

### Do's ✅
- Always use `async/await` for I/O operations
- Log at appropriate levels (DEBUG for dev, INFO for prod)
- Return early from functions to avoid deep nesting
- Use type hints everywhere
- Write tests before adding new features
- Keep functions small and single-purpose

### Don'ts ❌
- Never publish without explicit user confirmation
- Never store API keys in code or version control
- Never use blocking I/O in async routes
- Never catch all exceptions without logging
- Never modify published posts directly
- Never skip the review workflow, even for scheduled posts
