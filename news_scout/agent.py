from __future__ import annotations

"""Core news-scouting agent.

Workflow for each topic:
1. Ask the LLM to select up to 10 globally diverse news portals.
2. Fetch articles from each portal (via RSS feed or direct HTML scraping).
3. Ask the LLM to produce a synthesised daily report.
"""

import json
import logging
import time
from typing import Optional
from urllib.parse import urljoin, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "DNT": "1",
}
_REQUEST_TIMEOUT = 15  # seconds
_INTER_REQUEST_DELAY = 0.5  # seconds between site requests


class NewsScoutAgent:
    """LLM-driven agent that scouts news portals for a given topic."""

    def __init__(self, openai_client, model: str = "gpt-4o"):
        self.client = openai_client
        self.model = model

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str, temperature: float = 0.3) -> str:
        """Send a prompt to the LLM and return the text response."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        return response.choices[0].message.content.strip()

    @staticmethod
    def _parse_json_response(text: str):
        """Parse JSON from an LLM response, handling Markdown code fences."""
        text = text.strip()
        if "```" in text:
            parts = text.split("```")
            for i in range(1, len(parts), 2):
                candidate = parts[i].strip()
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    continue
        return json.loads(text)

    # ------------------------------------------------------------------
    # Source selection
    # ------------------------------------------------------------------

    def identify_sources(
        self, topic_name: str, topic_description: str
    ) -> list[dict]:
        """Ask the LLM to identify up to 10 globally diverse news portals."""
        prompt = (
            f'You are a news research expert. For the topic "{topic_name}" '
            f"({topic_description}), identify up to 10 diverse, global news "
            "portals with relevant, high-quality coverage.\n\n"
            "Requirements:\n"
            "- Include sources from different regions and perspectives "
            "(not only Western/US media).\n"
            "- For regional topics, include local/regional outlets as well as "
            "global ones.\n"
            "- Prefer outlets that publish RSS feeds.\n\n"
            "For each source provide:\n"
            '  "name"    : outlet name\n'
            '  "url"     : main website URL\n'
            '  "rss_url" : RSS feed URL (required)\n'
            '  "region"  : region or perspective '
            '(e.g. "global", "Middle East", "Asia")\n\n'
            "Example outlets for a Middle East topic: Al Jazeera, Haaretz, "
            "Tehran Times, Arab News, BBC, Reuters, France 24, Deutsche Welle, "
            "Xinhua, The Guardian.\n\n"
            "Return ONLY a JSON array – no explanation:\n"
            '[{"name":"...","url":"...","rss_url":"...","region":"..."}]'
        )
        content = self._call_llm(prompt)
        sources = self._parse_json_response(content)
        return sources[:10]

    # ------------------------------------------------------------------
    # Article fetching
    # ------------------------------------------------------------------

    def _find_rss_feed(self, url: str) -> Optional[str]:
        """Attempt to discover an RSS link from a site's <head> element."""
        try:
            resp = requests.get(
                url, headers=_REQUEST_HEADERS, timeout=_REQUEST_TIMEOUT
            )
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("link", type="application/rss+xml"):
                href = link.get("href", "")
                if href:
                    return href if href.startswith("http") else urljoin(url, href)
        except Exception:
            pass
        return None

    def _fetch_rss(
        self, source_name: str, rss_url: str, max_articles: int
    ) -> list[dict]:
        """Fetch articles from an RSS feed URL."""
        try:
            resp = requests.get(
                rss_url, headers=_REQUEST_HEADERS, timeout=_REQUEST_TIMEOUT
            )
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)
            if not feed.entries:
                return []
            articles = []
            for entry in feed.entries[:max_articles]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                raw_summary = entry.get("summary", entry.get("description", ""))
                summary = (
                    BeautifulSoup(raw_summary, "html.parser")
                    .get_text(separator=" ", strip=True)[:500]
                    if raw_summary
                    else ""
                )
                articles.append(
                    {
                        "source": source_name,
                        "title": title,
                        "summary": summary,
                        "url": entry.get("link", rss_url),
                        "published": entry.get("published", ""),
                    }
                )
            return articles
        except Exception as exc:
            logger.warning("RSS fetch failed for %s (%s): %s", source_name, rss_url, exc)
            return []

    def _scrape_headlines(
        self, source_name: str, url: str, max_articles: int
    ) -> list[dict]:
        """Scrape article headlines from a news website as a fallback."""
        try:
            time.sleep(_INTER_REQUEST_DELAY)
            resp = requests.get(url, headers=_REQUEST_HEADERS, timeout=_REQUEST_TIMEOUT)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            articles = []
            seen: set[str] = set()
            for tag in soup.find_all(["h1", "h2", "h3"]):
                text = tag.get_text(strip=True)
                if len(text) < 20 or text in seen:
                    continue
                seen.add(text)
                anchor = tag.find("a")
                article_url = url
                if anchor and anchor.get("href"):
                    href = anchor["href"]
                    if href.startswith("http"):
                        article_url = href
                    elif href.startswith("/"):
                        parsed = urlparse(url)
                        article_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                articles.append(
                    {
                        "source": source_name,
                        "title": text,
                        "summary": "",
                        "url": article_url,
                        "published": "",
                    }
                )
                if len(articles) >= max_articles:
                    break
            return articles
        except Exception as exc:
            logger.warning("Scraping failed for %s (%s): %s", source_name, url, exc)
            return []

    def fetch_articles(
        self, source: dict, max_articles: int = 5
    ) -> list[dict]:
        """Fetch articles from a source dict (tries RSS first, then scraping)."""
        name = source.get("name", "Unknown")

        # 1. Try the provided RSS URL
        rss_url = source.get("rss_url")
        if rss_url:
            articles = self._fetch_rss(name, rss_url, max_articles)
            if articles:
                return articles

        # 2. Try to auto-discover an RSS feed from the main URL
        main_url = source.get("url", "")
        if main_url:
            discovered = self._find_rss_feed(main_url)
            if discovered:
                articles = self._fetch_rss(name, discovered, max_articles)
                if articles:
                    return articles

        # 3. Fall back to HTML headline scraping
        if main_url:
            return self._scrape_headlines(name, main_url, max_articles)

        return []

    # ------------------------------------------------------------------
    # Report generation
    # ------------------------------------------------------------------

    def generate_report(
        self,
        topic_name: str,
        topic_description: str,
        articles: list[dict],
        sources: list[dict],
        language: str = "en",
    ) -> str:
        """Ask the LLM to produce a synthesised Markdown report."""
        if not articles:
            return f"# {topic_name}\n\nNo relevant articles found for this topic today.\n"

        sources_info = "\n".join(
            f"- {s['name']} ({s.get('region', 'unknown')})" for s in sources
        )
        articles_text = "\n\n".join(
            f"**[{a['source']}]** {a['title']}\n{a['summary']}\n{a['url']}"
            for a in articles[:40]  # cap to keep prompt within token limits
        )

        language_instruction = ""
        if language != "en":
            language_instruction = (
                f"\n\nIMPORTANT: Write the ENTIRE report in the language "
                f"with ISO 639-1 code '{language}'. All headings, analysis, "
                f"and prose must be in that language. Source names and URLs "
                f"may remain in their original form."
            )

        prompt = (
            f'You are an expert news analyst. Based on the articles about '
            f'"{topic_name}" ({topic_description}), write a comprehensive '
            "daily news report.\n\n"
            f"Sources consulted:\n{sources_info}\n\n"
            f"Articles:\n{articles_text}\n\n"
            "Write a report with these sections:\n"
            "1. **Executive Summary** – 2-3 sentences.\n"
            "2. **Key Developments** – bullet points for the most important stories.\n"
            "3. **Trends & Analysis** – what is trending, emerging, or fading.\n"
            "4. **Regional Perspectives** – different viewpoints where applicable.\n"
            "5. **Notable Sources & Links** – key articles with their URLs.\n\n"
            "Be analytical; synthesise across sources and highlight both consensus "
            "and divergences. Format the report in Markdown."
            f"{language_instruction}"
        )
        return self._call_llm(prompt, temperature=0.5)

    # ------------------------------------------------------------------
    # Email label translation
    # ------------------------------------------------------------------

    _DEFAULT_LABELS = {
        "report_title": "Daily News Scout Report",
        "date_label": "Date",
        "topic_prefix": "Topic",
        "subject_template": "Daily News Scout Report – {date}",
    }

    def translate_email_labels(self, language: str) -> dict:
        """Return translated email structural strings for *language*.

        When *language* is ``"en"``, returns English defaults without an LLM
        call.  For any other ISO 639-1 code a single LLM request translates
        the four label strings.
        """
        if language == "en":
            return dict(self._DEFAULT_LABELS)

        prompt = (
            f"Translate the following JSON values into the language with "
            f"ISO 639-1 code '{language}'. Keep the JSON keys unchanged and "
            f"keep the '{{date}}' placeholder in subject_template intact.\n\n"
            f"```json\n{json.dumps(self._DEFAULT_LABELS)}\n```\n\n"
            f"Return ONLY valid JSON – no explanation."
        )
        content = self._call_llm(prompt, temperature=0.0)
        try:
            labels = self._parse_json_response(content)
            # Ensure all required keys are present
            for key in self._DEFAULT_LABELS:
                if key not in labels:
                    labels[key] = self._DEFAULT_LABELS[key]
            return labels
        except Exception:
            logger.warning(
                "Failed to translate email labels for '%s'; using English defaults.",
                language,
            )
            return dict(self._DEFAULT_LABELS)

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def scout_topic(
        self, topic: dict, language: str = "en"
    ) -> tuple[str, list[dict]]:
        """Scout news for a topic dict and return (report_markdown, sources)."""
        name = topic.get("name", "Unknown Topic")
        description = topic.get("description", "")

        logger.info("Scouting: %s", name)

        # Step 1 – choose portals
        sources = self.identify_sources(name, description)
        logger.info("Sources selected: %s", [s.get("name") for s in sources])

        # Step 2 – collect articles
        all_articles: list[dict] = []
        for source in sources:
            logger.info("  Fetching from %s …", source.get("name"))
            all_articles.extend(self.fetch_articles(source))
            time.sleep(_INTER_REQUEST_DELAY)

        logger.info("Total articles collected: %d", len(all_articles))

        # Step 3 – generate report
        report = self.generate_report(
            name, description, all_articles, sources, language=language
        )
        return report, sources
