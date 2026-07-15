"""
app/prompts/hashtag_prompt.py
──────────────────────────────
Prompt templates for standalone hashtag generation.
"""

from __future__ import annotations

from typing import List, Optional


def build_hashtag_prompt(
    topic: str,
    post_content: str,
    preferred_hashtags: Optional[List[str]] = None,
    count: int = 10,
) -> str:
    """
    Build a prompt to regenerate hashtags for a given post.

    Args:
        topic: Post topic
        post_content: Full post content (for context)
        preferred_hashtags: User's preferred hashtag categories
        count: Number of hashtags to generate

    Returns:
        Formatted prompt string
    """
    preferred_section = ""
    if preferred_hashtags:
        preferred_section = (
            f"\nUser prefers hashtags in these categories: {', '.join(preferred_hashtags)}\n"
        )

    return f"""Generate {count} optimal LinkedIn hashtags for this post about {topic}.

Post content (first 300 chars):
\"\"\"{post_content[:300]}\"\"\"
{preferred_section}
Requirements:
- Mix of high-volume tags (millions of followers) and niche tags (thousands)
- No # prefix in your response
- All lowercase
- Relevant to both the topic and the specific content
- Include: 2-3 broad industry tags, 3-4 topic-specific tags, 2-3 niche tags

Return ONLY a JSON array of strings, example:
["artificialintelligence", "machinelearning", "python", "datascience", "aitools"]

Respond with ONLY the JSON array.
"""


HASHTAG_CATEGORIES = {
    "Artificial Intelligence": [
        "artificialintelligence", "ai", "machinelearning", "deeplearning",
        "generativeai", "llm", "chatgpt", "aitools", "futureofai",
    ],
    "Data Analytics": [
        "dataanalytics", "datascience", "businessintelligence", "powerbi",
        "tableau", "datavisualization", "bigdata", "dataengineering",
    ],
    "Python": [
        "python", "pythonprogramming", "pythondeveloper", "coding",
        "softwaredevelopment", "programming", "developer", "opensource",
    ],
    "Machine Learning": [
        "machinelearning", "ml", "deeplearning", "neuralnetworks",
        "mlops", "datascience", "predictiveanalytics", "ai",
    ],
    "Power BI": [
        "powerbi", "microsoftpowerbi", "datavisualization", "businessintelligence",
        "dax", "powerquery", "microsoftfabric", "analytics",
    ],
    "Cloud Computing": [
        "cloudcomputing", "aws", "azure", "googlecloud", "devops",
        "kubernetes", "docker", "serverless", "cloudnative",
    ],
    "Career Advice": [
        "careeradvice", "careergrowth", "personaldevelopment", "leadership",
        "productivity", "mindset", "success", "professionaldevelopment",
    ],
    "Productivity": [
        "productivity", "timemanagement", "worklifebalance", "focus",
        "habits", "efficiency", "personaldevelopment", "remotework",
    ],
    "Tech News": [
        "technews", "technology", "tech", "innovation", "startups",
        "futureofwork", "digitaltransformation", "techtrends",
    ],
    "Software Engineering": [
        "softwareengineering", "softwaredevelopment", "coding", "programming",
        "backend", "frontend", "fullstack", "agile", "cleancode",
    ],
}
