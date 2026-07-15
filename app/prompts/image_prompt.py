"""
app/prompts/image_prompt.py
───────────────────────────
Prompt templates for AI image generation (DALL-E 3).
Also contains keyword extraction for stock image search.
"""

from __future__ import annotations


def build_dalle_prompt(topic: str, post_hook: str) -> str:
    """
    Build a DALL-E 3 image generation prompt for a LinkedIn post.

    Args:
        topic: Post topic
        post_hook: Opening line of the post (for context)

    Returns:
        DALL-E 3 image prompt
    """
    return (
        f"A professional, modern, high-quality illustration for a LinkedIn post about {topic}. "
        f"Style: Clean corporate illustration with a vibrant color palette, "
        f"flat design with subtle gradients. "
        f"Include visual metaphors related to: {topic}. "
        f"No text, no letters, no words in the image. "
        f"Aspect ratio 16:9. Professional LinkedIn banner style. "
        f"Inspirational and motivational tone."
    )


def build_search_keywords(topic: str, post_hook: str) -> str:
    """
    Build a search query for stock image APIs (Unsplash, Pexels, Pixabay).

    Args:
        topic: Post topic
        post_hook: Opening line (for context)

    Returns:
        Search query string
    """
    topic_keywords = {
        "Artificial Intelligence": "artificial intelligence technology futuristic",
        "Data Analytics": "data analytics dashboard business chart",
        "Python": "python programming code developer laptop",
        "Machine Learning": "machine learning neural network technology",
        "Power BI": "business intelligence dashboard analytics data",
        "Cloud Computing": "cloud computing server technology network",
        "Career Advice": "professional career growth success business",
        "Productivity": "productivity workspace motivation focus office",
        "Tech News": "technology innovation future digital",
        "Software Engineering": "software engineering code development team",
    }
    return topic_keywords.get(topic, f"{topic} technology professional")


UNSPLASH_PHOTO_COLLECTIONS = {
    "Artificial Intelligence": ["3573009", "9013098"],
    "Data Analytics": ["9079917", "3573009"],
    "Python": ["9013098", "573009"],
    "Machine Learning": ["3573009", "9013098"],
    "Cloud Computing": ["9013098", "3573009"],
    "Career Advice": ["9079917", "3573009"],
    "Productivity": ["573009", "9079917"],
}
