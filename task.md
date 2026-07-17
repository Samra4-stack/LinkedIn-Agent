# Task List

- [x] Migrate from local SQLite to Supabase Postgres (Vercel Serverless compat)
- [x] Fix module-level `memory_store` initialization crashing Vercel at import time
- [x] Fix `api/index.py` top-level `app` static analysis issue
- [x] Assist user with deploying correctly to Vercel and connecting Supabase (Transaction Pooler)
- [x] Add ability to upload images from local gallery directly in the browser
  - [x] Update frontend preview HTML with compression logic
  - [x] Add backend FastAPI endpoint to receive Base64 images
  - [x] Update LinkedIn Service to decode base64 before upload
