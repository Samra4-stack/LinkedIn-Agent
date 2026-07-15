# 🚀 Getting Started Guide

> Step-by-step guide to set up and run the LinkedIn AI Agent from scratch.

---

## Prerequisites

| Requirement | Version | Check |
|---|---|---|
| Python | 3.12+ | `python --version` |
| pip | Latest | `pip --version` |
| Git | Any | `git --version` |

---

## 1. Installation

### Step 1 — Navigate to the project
```bash
cd linkedin-agent
```

### Step 2 — Create a virtual environment
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt.

### Step 3 — Install dependencies
```bash
pip install -r requirements.txt
```

This installs all required packages including FastAPI, SQLAlchemy, OpenAI, APScheduler, and more.

---

## 2. Configuration

### Step 4 — Create your `.env` file
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

### Step 5 — Open `.env` and fill in your API keys

```env
# ── Required: AI Provider (choose one) ──────────────────────
OPENAI_API_KEY=sk-your-openai-key-here
# OR
GEMINI_API_KEY=your-gemini-key-here
AI_PROVIDER=openai          # openai | gemini

# ── Required: LinkedIn ──────────────────────────────────────
LINKEDIN_CLIENT_ID=your-linkedin-client-id
LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
LINKEDIN_ACCESS_TOKEN=your-linkedin-access-token
LINKEDIN_PERSON_URN=urn:li:person:your-person-id

# ── Optional: Images (at least one recommended) ─────────────
UNSPLASH_API_KEY=your-unsplash-key
PEXELS_API_KEY=your-pexels-key
PIXABAY_API_KEY=your-pixabay-key

# ── Scheduler ───────────────────────────────────────────────
SCHEDULER_HOUR=9            # 9 AM
SCHEDULER_MINUTE=0
SCHEDULER_TIMEZONE=Asia/Karachi
```

> ⚠️ **Never commit `.env` to Git.** It's already in `.gitignore`.

---

## 3. Getting API Keys

### 🤖 OpenAI API Key
1. Go to [platform.openai.com](https://platform.openai.com)
2. Sign in → API Keys → **Create new secret key**
3. Copy the key (starts with `sk-`) → paste into `.env`

### 🌐 Google Gemini API Key (Free alternative)
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Click **Get API key** → **Create API key**
3. Copy and paste into `.env`
4. Set `AI_PROVIDER=gemini` in `.env`

### 🖼️ Image APIs (Free)

**Unsplash** (50 requests/hour free):
1. Go to [unsplash.com/developers](https://unsplash.com/developers)
2. **New Application** → fill form → copy **Access Key**

**Pexels** (200 requests/hour free):
1. Go to [pexels.com/api](https://www.pexels.com/api/)
2. **Your API** → copy key

**Pixabay** (100 requests/minute free):
1. Go to [pixabay.com/api/docs](https://pixabay.com/api/docs/)
2. Log in → copy your API key

### 🔗 LinkedIn API Setup

**Step A — Create a LinkedIn App:**
1. Go to [linkedin.com/developers/apps](https://www.linkedin.com/developers/apps)
2. Click **Create app**
3. Fill in: App Name, LinkedIn Page, Logo
4. Under **Products**, request: **Share on LinkedIn** and **Sign In with LinkedIn**
5. Copy `Client ID` and `Client Secret` to `.env`

**Step B — Get your Access Token:**
1. Start the server: `uvicorn app.main:app --reload`
2. Open: `http://localhost:8000/auth/linkedin`
3. Visit the `auth_url` in your browser
4. Authorize the app
5. Copy the `access_token` from the callback response
6. Paste it as `LINKEDIN_ACCESS_TOKEN` in `.env`

**Step C — Get your Person URN:**
1. After getting a token, call: `GET http://localhost:8000/api/v1/settings`
2. Or make a request to `https://api.linkedin.com/v2/userinfo` with your token
3. The `sub` field is your person ID
4. Set `LINKEDIN_PERSON_URN=urn:li:person:{sub}`

---

## 4. Running the Application

### Step 6 — Start the FastAPI server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO     Starting LinkedIn AI Agent | env=development
INFO     Database tables created successfully
INFO     Scheduler started | daily job at 09:00 Asia/Karachi
INFO     Uvicorn running on http://0.0.0.0:8000
```

### Step 7 — Open Swagger UI
Navigate to: **http://localhost:8000/docs**

You'll see the full interactive API documentation with all endpoints.

---

## 5. Your First Post — Step by Step

### Step 1: Generate a post
In Swagger UI, click `POST /api/v1/generate` → **Try it out** → Execute:
```json
{
  "topic": "Artificial Intelligence",
  "style": "professional"
}
```

Response:
```json
{
  "draft_id": 1,
  "topic": "Artificial Intelligence",
  "status": "pending_review",
  "preview_url": "/preview/1"
}
```

### Step 2: Preview the post
Click `GET /api/v1/preview/{draft_id}` → Enter `draft_id: 1` → Execute.

Review the full post including:
- Hook, body, CTA
- Hashtags
- Image URL
- Relevant links

### Step 3: Edit (optional)
If you want to change something:
```json
POST /api/v1/edit
{
  "draft_id": 1,
  "field": "hook",
  "value": "🔥 AI is changing EVERYTHING about how we work."
}
```

### Step 4: Approve
```
POST /api/v1/preview/1/approve
```

### Step 5: Publish
```json
POST /api/v1/publish
{
  "draft_id": 1,
  "confirm": true
}
```

Your post is now live on LinkedIn! 🎉

---

## 6. Configuring the Daily Scheduler

The agent runs a daily job at 9:00 AM (Karachi time) by default.

### Change the schedule:
```json
POST /api/v1/schedule
{
  "hour": 8,
  "minute": 30,
  "timezone": "Asia/Karachi",
  "enabled": true
}
```

### Test it right now:
```
POST /api/v1/schedule/trigger
```

This runs the job immediately — a new draft will appear in:
```
GET /api/v1/history/pending
```

### Pause the scheduler (vacation):
```
POST /api/v1/schedule/pause
```

---

## 7. Managing Topics

### View current topics:
```
GET /api/v1/settings
```

### Update topics:
```json
PUT /api/v1/settings
{
  "topics": [
    "Artificial Intelligence",
    "Python",
    "Data Analytics",
    "Career Advice",
    "Cloud Computing"
  ]
}
```

### The agent automatically:
- Rotates through topics to avoid repetition
- Avoids topics used in the last 7 days
- Prioritizes topics you mark as favorites

---

## 8. Testing the APIs

### Using Swagger UI (Recommended)
1. Open `http://localhost:8000/docs`
2. Click any endpoint
3. Click **Try it out**
4. Fill the request body
5. Click **Execute**

### Using curl
```bash
# Health check
curl http://localhost:8000/health

# Generate a post
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"topic": "Python"}'

# Get preview
curl http://localhost:8000/api/v1/preview/1

# Approve
curl -X POST http://localhost:8000/api/v1/preview/1/approve

# Publish
curl -X POST http://localhost:8000/api/v1/publish \
  -H "Content-Type: application/json" \
  -d '{"draft_id": 1, "confirm": true}'
```

### Using Python (httpx)
```python
import httpx

BASE = "http://localhost:8000/api/v1"

# Generate
r = httpx.post(f"{BASE}/generate", json={"topic": "AI"})
draft_id = r.json()["draft_id"]

# Preview
r = httpx.get(f"{BASE}/preview/{draft_id}")
print(r.json()["full_content"])

# Approve
httpx.post(f"{BASE}/preview/{draft_id}/approve")

# Publish
r = httpx.post(f"{BASE}/publish", json={"draft_id": draft_id, "confirm": True})
print(r.json())
```

---

## 9. Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=html
# Open htmlcov/index.html to view coverage report

# Run specific test file
pytest tests/test_api_endpoints.py -v

# Run specific test
pytest tests/test_api_endpoints.py::TestGenerateEndpoint::test_generate_with_topic -v
```

---

## 10. Viewing Logs

Logs are written to `./logs/agent.log` and the console.

```bash
# Tail logs in real time (PowerShell)
Get-Content .\logs\agent.log -Wait -Tail 50

# Tail logs (Linux/macOS)
tail -f logs/agent.log
```

Log levels:
- `DEBUG` — Very detailed (dev only)
- `INFO` — Normal operations
- `WARNING` — Recoverable issues
- `ERROR` — Failures that need attention

---

## 11. Troubleshooting

### ❌ "OPENAI_API_KEY is not configured"
- Check your `.env` file exists and has the key
- Make sure the key starts with `sk-`
- Restart the server after changing `.env`

### ❌ "LinkedIn access token is invalid or expired"
- LinkedIn tokens expire after 60 days
- Re-authorize via `GET /auth/linkedin` → follow the OAuth flow
- Update `LINKEDIN_ACCESS_TOKEN` in `.env`

### ❌ "Draft must be APPROVED before publishing"
- You skipped the approve step
- Call `POST /api/v1/preview/{draft_id}/approve` first

### ❌ No images appearing
- Check your image API keys are set in `.env`
- Try setting `IMAGE_PROVIDER_PRIORITY=dalle` (uses your OpenAI key)
- Image will be empty if all providers fail — post still works

### ❌ "Could not load memory file"
- The `data/` directory will be created automatically on first run
- If you see this on first startup, it's normal — memory starts fresh

### ❌ Port 8000 already in use
```bash
# Use a different port
uvicorn app.main:app --reload --port 8001
```

### ❌ Module not found errors
```bash
# Make sure venv is activated
venv\Scripts\activate       # Windows
source venv/bin/activate    # macOS/Linux

# Reinstall dependencies
pip install -r requirements.txt
```

---

## 12. Frequently Asked Questions

**Q: Will the agent ever post without my permission?**
> No. The scheduler only **generates drafts**. Publishing always requires you to:
> 1. Approve the draft (`POST /preview/{id}/approve`)
> 2. Explicitly publish with `confirm: true`

**Q: How do I stop the daily auto-generation?**
> Call `POST /api/v1/schedule/pause` or set `scheduler_enabled: false` in settings.

**Q: Can I use both OpenAI and Gemini?**
> Yes. Set `AI_PROVIDER=openai` as primary. If OpenAI fails, Gemini is used as fallback automatically.

**Q: How many posts can I generate per day?**
> As many as you want via `POST /generate`. The daily scheduler generates 1 automatically. LinkedIn itself has no API rate limit for posting frequency, but posting too often reduces engagement.

**Q: How does the memory/deduplication work?**
> The agent stores every generated post's topic, content hash, and angle in `data/memory.json` and SQLite. Before generating, it checks what was created in the last 30 days and picks a fresh topic and angle.

**Q: Can I use a custom topic not in the list?**
> Yes. Pass `"topic": "Your Custom Topic"` to `POST /generate`. Any string is accepted.

**Q: How do I migrate to PostgreSQL?**
> 1. Install: `pip install psycopg2-binary`
> 2. Update `.env`: `DATABASE_URL=postgresql://user:pass@localhost/linkedin_agent`
> 3. Restart the server — tables are auto-created on startup.

**Q: What LinkedIn permissions does the app need?**
> - `openid` — Basic login
> - `profile` — Profile info
> - `email` — Email address
> - `w_member_social` — **Required for posting**

---

## 13. Directory Reference

After running the server, these directories are auto-created:

```
linkedin-agent/
├── data/
│   └── memory.json          ← Agent memory (topics, hashes, prefs)
├── logs/
│   └── agent.log            ← Rotating log file
└── linkedin_agent.db        ← SQLite database
```

---

*Built with ❤️ using Python 3.12, FastAPI, OpenAI, and LinkedIn API*
