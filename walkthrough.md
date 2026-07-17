# Project Walkthrough: Cloud Migration, Gallery Uploads, & Dynamic Scheduling

## 1. Cloud Architecture & Stability
- The system is now successfully deployed to Vercel and connected to Supabase using a transaction pooler URL (port 6543).
- **Fixed the serverless crash** by converting the `MemoryStore` into a lazy-loading singleton, preventing disk writes during Vercel's immutable module import phase.
- Fixed the static analysis issue in `api/index.py` allowing Vercel to locate the `app` instance correctly.

## 2. Image Gallery Uploads
- Added a **"Upload from Gallery"** button to the Draft Preview page (`preview.html`).
- Implemented **browser-side image compression**. When a user selects a photo on their phone, JavaScript compresses it to a standard size (max 1200px) and converts it to a JPEG Base64 string under 1MB. This safely bypasses Vercel's strict 4.5MB payload limit.
- Added a new backend endpoint `/api/v1/preview/{id}/upload-image` that saves this Base64 string directly into the Supabase database.
- Upgraded the `LinkedInService` to automatically detect Base64 strings and decode them right before uploading to LinkedIn's API, removing the need for an external file storage bucket!

## 3. Custom Topic Input
- Added a new **"💡 Generate New Topic"** button to the Preview UI.
- Users can click this button, type their desired topic, and the system automatically generates a new draft and redirects the user to the newly generated preview link.

## 4. Professional Emoji Instructions
- Upgraded the AI prompt instructions (`post_prompt.py`) to explicitly instruct the LLM to strategically use professional emojis (e.g., 🚀, 💡, 📊, ✅) instead of overly casual ones.

## 5. Dynamic Cloud Scheduling
- In serverless environments, static cron files usually lock users into a fixed time.
- Implemented a clever **GitHub Actions** workaround: A new `.github/workflows/scheduler.yml` pings the `/api/v1/schedule/poll` endpoint every 5 minutes.
- The `poll` endpoint checks the database's user-defined scheduling time. If the current time is within 5 minutes of the requested time, the background job executes successfully. This fully restores dynamic UI scheduling in a serverless environment!
