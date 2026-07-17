"""
app/services/link_service.py
─────────────────────────────
Searches for high-quality, relevant links to attach to LinkedIn posts.
Uses DuckDuckGo Instant Answer API (no API key required) and curated
source mappings as fallback.
"""

from __future__ import annotations

import urllib.parse
from typing import Dict, List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.utils.helpers import is_valid_url
from app.utils.logger import get_logger

log = get_logger(__name__)

TIMEOUT = httpx.Timeout(10.0)


# Curated high-quality source fallbacks per topic
CURATED_LINKS: Dict[str, List[Dict[str, str]]] = {
    "Artificial Intelligence": [
        {"title": "OpenAI Research", "url": "https://openai.com/research"},
        {"title": "Google AI Blog", "url": "https://ai.googleblog.com"},
        {"title": "AI News - MIT Technology Review", "url": "https://www.technologyreview.com/topic/artificial-intelligence/"},
    ],
    "Data Analytics": [
        {"title": "Microsoft Power BI Blog", "url": "https://powerbi.microsoft.com/en-us/blog/"},
        {"title": "Towards Data Science", "url": "https://towardsdatascience.com"},
        {"title": "Google Analytics Academy", "url": "https://analytics.google.com/analytics/academy/"},
    ],
    "Python": [
        {"title": "Official Python Docs", "url": "https://docs.python.org/3/"},
        {"title": "Real Python Tutorials", "url": "https://realpython.com"},
        {"title": "PyPI - Package Index", "url": "https://pypi.org"},
    ],
    "Machine Learning": [
        {"title": "Papers With Code", "url": "https://paperswithcode.com"},
        {"title": "Hugging Face Blog", "url": "https://huggingface.co/blog"},
        {"title": "Google ML Education", "url": "https://developers.google.com/machine-learning"},
    ],
    "Power BI": [
        {"title": "Microsoft Power BI Docs", "url": "https://learn.microsoft.com/en-us/power-bi/"},
        {"title": "Power BI Community", "url": "https://community.fabric.microsoft.com/t5/Power-BI-Community/ct-p/PBI_Community"},
        {"title": "SQLBI DAX Guide", "url": "https://dax.guide"},
    ],
    "Cloud Computing": [
        {"title": "AWS What's New", "url": "https://aws.amazon.com/new/"},
        {"title": "Azure Updates", "url": "https://azure.microsoft.com/en-us/updates/"},
        {"title": "Google Cloud Blog", "url": "https://cloud.google.com/blog"},
    ],
    "Career Advice": [
        {"title": "LinkedIn Career Blog", "url": "https://www.linkedin.com/blog/member/career"},
        {"title": "Harvard Business Review", "url": "https://hbr.org/topic/career-planning"},
        {"title": "Glassdoor Career Tips", "url": "https://www.glassdoor.com/blog/guide/career-advice/"},
    ],
    "Productivity": [
        {"title": "Notion Blog", "url": "https://www.notion.so/blog"},
        {"title": "Todoist Inspiration Hub", "url": "https://todoist.com/inspiration"},
        {"title": "Atomic Habits (Book)", "url": "https://jamesclear.com/atomic-habits"},
    ],
    "Tech News": [
        {"title": "TechCrunch", "url": "https://techcrunch.com"},
        {"title": "The Verge", "url": "https://www.theverge.com"},
        {"title": "Hacker News", "url": "https://news.ycombinator.com"},
    ],
    "Software Engineering": [
        {"title": "GitHub Blog", "url": "https://github.blog"},
        {"title": "Stack Overflow Blog", "url": "https://stackoverflow.blog"},
        {"title": "Martin Fowler's Blog", "url": "https://martinfowler.com"},
    ],
}


class LinkService:
    """
    Finds high-quality, relevant links for LinkedIn posts.

    Strategy:
    1. Search DuckDuckGo Instant Answer API (free, no key needed)
    2. Fall back to curated topic-specific links
    """

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=1, max=5),
        retry=retry_if_exception_type(httpx.RequestError),
        reraise=False,
    )
    async def find_links(
        self,
        topic: str,
        post_content: str,
        count: int = 3,
    ) -> List[Dict[str, str]]:
        """
        Find relevant links for a post.

        Args:
            topic: Post topic
            post_content: Post content (for context)
            count: Number of links to return (1–3)

        Returns:
            List of dicts with 'title' and 'url' keys
        """
        log.info(f"Searching for links | topic={topic} | count={count}")

        links = []

        # Try DuckDuckGo first
        try:
            ddg_links = await self._search_duckduckgo(topic)
            links.extend(ddg_links)
        except Exception as e:
            log.warning(f"DuckDuckGo search failed: {e}")

        # Supplement/fallback with curated links
        import random
        curated = CURATED_LINKS.get(topic, CURATED_LINKS.get("Tech News", [])).copy()
        random.shuffle(curated)
        for link in curated:
            if len(links) >= count:
                break
            # Avoid duplicates
            if not any(l["url"] == link["url"] for l in links):
                links.append(link)

        result = links[:count]
        log.info(f"Found {len(result)} links for topic={topic}")
        return result

    async def _search_duckduckgo(self, topic: str) -> List[Dict[str, str]]:
        """
        Query DuckDuckGo Instant Answer API for topic-related links.

        Note: This is DuckDuckGo's free public API — no authentication needed.
        Returns related topics from DuckDuckGo's knowledge base.
        """
        query = f"{topic} best resources guide tutorial"
        encoded_query = urllib.parse.quote(query)

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(
                f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_redirect=1&no_html=1",
                headers={"User-Agent": "LinkedIn-AI-Agent/1.0"},
            )
            response.raise_for_status()
            data = response.json()

        links = []

        # Extract related topics
        for related in data.get("RelatedTopics", [])[:5]:
            if isinstance(related, dict) and "FirstURL" in related:
                url = related.get("FirstURL", "")
                text = related.get("Text", "")
                if url and is_valid_url(url) and text:
                    links.append({
                        "title": text[:80].strip(),
                        "url": url,
                    })

        # Extract abstract URL if available
        abstract_url = data.get("AbstractURL", "")
        abstract_source = data.get("AbstractSource", "")
        if abstract_url and is_valid_url(abstract_url):
            links.insert(0, {
                "title": f"{abstract_source or topic} — Overview",
                "url": abstract_url,
            })

        return links[:3]

    def get_urls_only(self, links: List[Dict[str, str]]) -> List[str]:
        """Extract just the URLs from a list of link dicts."""
        return [link["url"] for link in links if "url" in link]


# Module-level singleton
link_service = LinkService()
