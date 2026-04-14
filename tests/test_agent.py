"""Tests for NewsScoutAgent."""

import json
from unittest.mock import MagicMock, patch

import pytest

from news_scout.agent import NewsScoutAgent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_llm_response(content: str) -> MagicMock:
    """Return a minimal mock that mimics an OpenAI chat completion response."""
    resp = MagicMock()
    resp.choices[0].message.content = content
    return resp


def _make_feed_entry(
    title: str = "Headline",
    summary: str = "Summary.",
    link: str = "https://example.com/art",
    published: str = "",
) -> MagicMock:
    """Return a feedparser-style dict-like entry mock."""
    entry = MagicMock()
    entry.get.side_effect = lambda key, default="": {
        "title": title,
        "summary": summary,
        "link": link,
        "published": published,
    }.get(key, default)
    return entry


@pytest.fixture()
def mock_client() -> MagicMock:
    return MagicMock()


@pytest.fixture()
def agent(mock_client) -> NewsScoutAgent:
    return NewsScoutAgent(mock_client, model="gpt-4o")


# ---------------------------------------------------------------------------
# _parse_json_response
# ---------------------------------------------------------------------------

class TestParseJsonResponse:
    def test_plain_json(self, agent):
        data = agent._parse_json_response('[{"name": "BBC"}]')
        assert data == [{"name": "BBC"}]

    def test_json_in_code_fence(self, agent):
        text = '```json\n[{"name": "Reuters"}]\n```'
        data = agent._parse_json_response(text)
        assert data == [{"name": "Reuters"}]

    def test_json_in_plain_fence(self, agent):
        text = '```\n[{"name": "Al Jazeera"}]\n```'
        data = agent._parse_json_response(text)
        assert data == [{"name": "Al Jazeera"}]

    def test_invalid_json_raises(self, agent):
        with pytest.raises(json.JSONDecodeError):
            agent._parse_json_response("not json")


# ---------------------------------------------------------------------------
# identify_sources
# ---------------------------------------------------------------------------

class TestIdentifySources:
    def test_returns_sources_list(self, agent, mock_client):
        sources_json = json.dumps([
            {"name": "BBC News", "url": "https://bbc.com",
             "rss_url": "https://feeds.bbci.co.uk/news/rss.xml", "region": "global"},
            {"name": "Al Jazeera", "url": "https://aljazeera.com",
             "rss_url": "https://aljazeera.com/rss.xml", "region": "Middle East"},
        ])
        mock_client.chat.completions.create.return_value = _make_llm_response(
            sources_json
        )

        sources = agent.identify_sources("Middle East Conflict", "Conflict in Gaza")

        assert len(sources) == 2
        assert sources[0]["name"] == "BBC News"
        assert sources[1]["region"] == "Middle East"

    def test_handles_markdown_code_fence(self, agent, mock_client):
        sources_json = (
            '```json\n[{"name": "Reuters", "url": "https://reuters.com", '
            '"rss_url": "https://feeds.reuters.com/reuters/topNews", "region": "global"}]\n```'
        )
        mock_client.chat.completions.create.return_value = _make_llm_response(
            sources_json
        )

        sources = agent.identify_sources("AI", "AI news")

        assert len(sources) == 1
        assert sources[0]["name"] == "Reuters"

    def test_limits_to_10_sources(self, agent, mock_client):
        big_list = [
            {"name": f"Source{i}", "url": f"https://s{i}.com",
             "rss_url": f"https://s{i}.com/rss", "region": "global"}
            for i in range(15)
        ]
        mock_client.chat.completions.create.return_value = _make_llm_response(
            json.dumps(big_list)
        )

        sources = agent.identify_sources("Topic", "Description")

        assert len(sources) <= 10


# ---------------------------------------------------------------------------
# _fetch_rss
# ---------------------------------------------------------------------------

class TestFetchRss:
    def test_returns_articles_from_valid_feed(self, agent):
        entry = _make_feed_entry(
            title="Ceasefire talks resume",
            summary="Negotiations resumed in Cairo.",
            link="https://example.com/article1",
            published="Mon, 01 Jan 2024 12:00:00 GMT",
        )
        mock_feed = MagicMock()
        mock_feed.entries = [entry]

        with patch("requests.get") as mock_get, \
             patch("feedparser.parse", return_value=mock_feed):
            mock_get.return_value = MagicMock(status_code=200, content=b"<rss/>")
            mock_get.return_value.raise_for_status = MagicMock()

            articles = agent._fetch_rss("Test Source", "https://example.com/rss", 5)

        assert len(articles) == 1
        assert articles[0]["title"] == "Ceasefire talks resume"
        assert articles[0]["source"] == "Test Source"

    def test_returns_empty_list_on_empty_feed(self, agent):
        mock_feed = MagicMock()
        mock_feed.entries = []

        with patch("requests.get") as mock_get, \
             patch("feedparser.parse", return_value=mock_feed):
            mock_get.return_value = MagicMock(status_code=200, content=b"<rss/>")
            mock_get.return_value.raise_for_status = MagicMock()

            articles = agent._fetch_rss("Source", "https://example.com/rss", 5)

        assert articles == []

    def test_returns_empty_list_on_request_error(self, agent):
        with patch("requests.get", side_effect=Exception("timeout")):
            articles = agent._fetch_rss("Source", "https://example.com/rss", 5)

        assert articles == []


# ---------------------------------------------------------------------------
# fetch_articles (integration of RSS + scrape fallback)
# ---------------------------------------------------------------------------

class TestFetchArticles:
    def test_uses_rss_when_available(self, agent):
        mock_feed = MagicMock()
        mock_feed.entries = [_make_feed_entry(title="Test headline", summary="Summary text.")]

        with patch("requests.get") as mock_get, \
             patch("feedparser.parse", return_value=mock_feed):
            mock_get.return_value = MagicMock(status_code=200, content=b"<rss/>")
            mock_get.return_value.raise_for_status = MagicMock()

            source = {
                "name": "Example",
                "url": "https://example.com",
                "rss_url": "https://example.com/rss",
            }
            articles = agent.fetch_articles(source)

        assert len(articles) == 1
        assert articles[0]["source"] == "Example"

    def test_returns_empty_when_all_sources_fail(self, agent):
        with patch("requests.get", side_effect=Exception("network error")), \
             patch("feedparser.parse", side_effect=Exception("parse error")):
            source = {
                "name": "Bad Source",
                "url": "https://badsource.example",
                "rss_url": "https://badsource.example/rss",
            }
            articles = agent.fetch_articles(source)

        assert articles == []


# ---------------------------------------------------------------------------
# generate_report
# ---------------------------------------------------------------------------

class TestGenerateReport:
    def test_returns_report_when_articles_present(self, agent, mock_client):
        mock_client.chat.completions.create.return_value = _make_llm_response(
            "# Middle East Conflict\n\nSome analysis."
        )
        articles = [
            {
                "source": "BBC",
                "title": "Talks stall",
                "summary": "Negotiations broke down.",
                "url": "https://bbc.com/art1",
                "published": "",
            }
        ]
        sources = [{"name": "BBC", "region": "global"}]

        report = agent.generate_report(
            "Middle East Conflict", "Conflict news", articles, sources
        )

        assert "Middle East Conflict" in report
        mock_client.chat.completions.create.assert_called_once()

    def test_returns_no_articles_message_without_llm_call(self, agent, mock_client):
        report = agent.generate_report("Empty Topic", "desc", [], [])

        assert "No relevant articles" in report
        mock_client.chat.completions.create.assert_not_called()

    def test_language_instruction_added_for_non_english(self, agent, mock_client):
        mock_client.chat.completions.create.return_value = _make_llm_response(
            "# Raport\n\nAnaliza."
        )
        articles = [
            {
                "source": "BBC",
                "title": "Headline",
                "summary": "Summary.",
                "url": "https://bbc.com/art1",
                "published": "",
            }
        ]
        sources = [{"name": "BBC", "region": "global"}]

        agent.generate_report("Topic", "desc", articles, sources, language="pl")

        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        assert "'pl'" in prompt
        assert "ENTIRE report" in prompt

    def test_no_language_instruction_for_english(self, agent, mock_client):
        mock_client.chat.completions.create.return_value = _make_llm_response(
            "# Report\n\nAnalysis."
        )
        articles = [
            {
                "source": "BBC",
                "title": "Headline",
                "summary": "Summary.",
                "url": "https://bbc.com/art1",
                "published": "",
            }
        ]
        sources = [{"name": "BBC", "region": "global"}]

        agent.generate_report("Topic", "desc", articles, sources, language="en")

        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        assert "ENTIRE report" not in prompt


# ---------------------------------------------------------------------------
# translate_email_labels
# ---------------------------------------------------------------------------

class TestTranslateEmailLabels:
    def test_returns_english_defaults_without_llm_call(self, agent, mock_client):
        labels = agent.translate_email_labels("en")

        assert labels["report_title"] == "Daily News Scout Report"
        assert labels["date_label"] == "Date"
        assert labels["topic_prefix"] == "Topic"
        assert "{date}" in labels["subject_template"]
        mock_client.chat.completions.create.assert_not_called()

    def test_calls_llm_for_non_english(self, agent, mock_client):
        translated = json.dumps({
            "report_title": "Codzienny Raport",
            "date_label": "Data",
            "topic_prefix": "Temat",
            "subject_template": "Codzienny Raport – {date}",
        })
        mock_client.chat.completions.create.return_value = _make_llm_response(
            translated
        )

        labels = agent.translate_email_labels("pl")

        assert labels["report_title"] == "Codzienny Raport"
        assert labels["date_label"] == "Data"
        mock_client.chat.completions.create.assert_called_once()

    def test_falls_back_to_english_on_parse_error(self, agent, mock_client):
        mock_client.chat.completions.create.return_value = _make_llm_response(
            "not valid json at all"
        )

        labels = agent.translate_email_labels("de")

        assert labels["report_title"] == "Daily News Scout Report"

    def test_fills_missing_keys_from_defaults(self, agent, mock_client):
        partial = json.dumps({
            "report_title": "Rapport Quotidien",
            "date_label": "Date",
        })
        mock_client.chat.completions.create.return_value = _make_llm_response(
            partial
        )

        labels = agent.translate_email_labels("fr")

        assert labels["report_title"] == "Rapport Quotidien"
        assert labels["topic_prefix"] == "Topic"  # English fallback
        assert "{date}" in labels["subject_template"]  # English fallback


# ---------------------------------------------------------------------------
# scout_topic
# ---------------------------------------------------------------------------

class TestScoutTopic:
    def test_returns_report_and_sources(self, agent, mock_client):
        sources_json = json.dumps([
            {"name": "BBC", "url": "https://bbc.com",
             "rss_url": "https://feeds.bbci.co.uk/rss.xml", "region": "global"},
        ])
        report_text = "# Report\n\nKey findings here."

        # First LLM call → identify_sources; second → generate_report
        mock_client.chat.completions.create.side_effect = [
            _make_llm_response(sources_json),
            _make_llm_response(report_text),
        ]

        mock_feed = MagicMock()
        mock_feed.entries = [_make_feed_entry(title="Headline", summary="Body text.", link="https://bbc.com/art")]

        with patch("requests.get") as mock_get, \
             patch("feedparser.parse", return_value=mock_feed):
            mock_get.return_value = MagicMock(status_code=200, content=b"<rss/>")
            mock_get.return_value.raise_for_status = MagicMock()

            topic = {"name": "Middle East", "description": "Conflict news"}
            report, sources = agent.scout_topic(topic)

        assert "Report" in report
        assert len(sources) == 1
        assert sources[0]["name"] == "BBC"
