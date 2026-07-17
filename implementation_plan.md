# Dynamic Scheduling, Custom Topics & Emojis

## 1. Dynamic Scheduling (GitHub Actions)
- I will configure the GitHub Action to run every **5 minutes** (e.g., `*/5 * * * *`).
- **Important Note:** GitHub Actions has a strict minimum limit of 5 minutes. It is physically impossible to schedule it every 2 or 3 minutes on GitHub. With 5 minutes, if you schedule a post for 10:02, it might run at 10:05. This is the absolute fastest allowed by free cloud providers.
- The polling logic will check the database and trigger the generation if the current time is within the last 5 minutes.

## 2. Custom Topic from Preview Page
- I will add a new button to the `preview.html` page: **"💡 Generate New Custom Topic"**.
- When you click it, a popup will ask you: *"Enter your custom topic:"*
- The page will send this to the AI, wait for it to generate the new draft, and automatically redirect you to the new draft's preview page.

## 3. Professional Emojis
- I will update the AI system instructions in `app/prompts/post_prompt.py`.
- The AI will be explicitly instructed to: *"Strategically use a few professional emojis (e.g., 🚀, 💡, 📊, ✅) to make the post engaging and readable, but avoid overusing casual emojis."*

## User Review Required
> [!WARNING]
> Please confirm you understand that the scheduling "alarm" can only check every **5 minutes** (due to GitHub's hard limit). If this is acceptable, I will begin coding all three features immediately!
