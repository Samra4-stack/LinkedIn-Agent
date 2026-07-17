"""
app/prompts/post_prompt.py
──────────────────────────
Prompt templates for LinkedIn post generation.
Uses Jinja2-style Python string formatting for dynamic injection.
"""

from __future__ import annotations

from typing import List, Optional


SYSTEM_PROMPT = """You are an expert LinkedIn content creator with 10+ years of experience 
building personal brands for tech professionals. You write posts that:

- Start with a powerful hook that stops the scroll
- Share genuine insights, not generic advice
- Tell stories that resonate with professionals
- Drive real engagement and conversations
- Position the author as a thought leader

Your writing style:
- Conversational yet professional
- Data-driven when possible
- Personal and authentic
- Action-oriented
- Clear and scannable (short paragraphs, line breaks)

LinkedIn post formatting rules:
- Use line breaks generously (every 1-2 sentences)
- Start with an emoji on the opening line for visual appeal
- Use bullet points or numbered lists where appropriate
- End with a clear CTA that invites comments/engagement
- Keep total length between 500-2000 characters for optimal reach
- Strategically use a few professional emojis (e.g., 🚀, 💡, 📊, ✅) to make the post engaging and readable, but avoid overusing casual emojis.
"""


def build_post_prompt(
    topic: str,
    style: str = "professional",
    custom_instructions: Optional[str] = None,
    recent_topics: Optional[List[str]] = None,
    preferred_hashtags: Optional[List[str]] = None,
    language: str = "English",
) -> str:
    """
    Build the user-facing prompt for LinkedIn post generation.

    Args:
        topic: Main topic of the post
        style: Writing style (professional | casual | storytelling | educational)
        custom_instructions: Optional extra instructions from the user
        recent_topics: List of recently used topics/angles to avoid
        preferred_hashtags: User's preferred hashtag categories
        language: Output language

    Returns:
        Formatted prompt string
    """
    avoid_section = ""
    if recent_topics:
        recent_str = "\n".join(f"  - {t}" for t in recent_topics[:10])
        avoid_section = f"""
IMPORTANT - Avoid these recently covered angles:
{recent_str}
Come up with a FRESH angle that hasn't been covered recently.
"""

    hashtag_hint = ""
    if preferred_hashtags:
        hashtag_hint = f"Consider including hashtags from these preferred categories: {', '.join(preferred_hashtags[:5])}"

    style_descriptions = {
        "professional": "authoritative, insightful, thought-leadership tone",
        "casual": "friendly, approachable, conversational tone",
        "storytelling": "narrative-driven with a personal story or case study",
        "educational": "teaching-focused with actionable tips and frameworks",
    }
    style_desc = style_descriptions.get(style, style_descriptions["professional"])

    prompt = f"""Create a high-quality LinkedIn post about: **{topic}**

Writing Style: {style} — {style_desc}
Language: {language}
{avoid_section}

Structure your response as a JSON object with these exact fields:

{{
  "hook": "The opening line(s) — powerful, scroll-stopping, 1-3 sentences max",
  "body": "The main content — insights, story, tips, or frameworks. Use line breaks and formatting for readability.",
  "cta": "A specific call-to-action that invites engagement (comment, share, DM, etc.)",
  "full_post": "The complete assembled post ready to publish. Combine hook + body + CTA with proper LinkedIn formatting and emojis.",
  "hashtags": ["hashtag1", "hashtag2", "..."],
  "topic_angle": "A brief description of the specific angle/perspective taken"
}}

Requirements:
- full_post must be between 500-2000 characters
- hashtags: exactly 8-10 relevant hashtags (no # prefix, lowercase)
- The post should feel authentic, NOT generic
- Include at least one specific insight, statistic, or story element
- End with an engaging question or clear CTA
{hashtag_hint}

Respond with ONLY the JSON object, no extra text.
"""
    return prompt


def build_variation_prompt(original_post: str, variation_instructions: str) -> str:
    """
    Build a prompt to create a variation of an existing post.

    Args:
        original_post: The original post content
        variation_instructions: What to change

    Returns:
        Prompt for generating a variation
    """
    return f"""Here is an existing LinkedIn post:

---
{original_post}
---

Create an improved variation with these changes: {variation_instructions}

Return the result as a JSON object with the same structure as before:
{{
  "hook": "...",
  "body": "...",
  "cta": "...",
  "full_post": "...",
  "hashtags": ["..."],
  "topic_angle": "..."
}}

Respond with ONLY the JSON object.
"""
