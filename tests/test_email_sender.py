"""Tests for EmailSender (Azure Communication Services backend)."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from news_scout.email_sender import EmailSender

_FAKE_CONN_STR = (
    "endpoint=https://example.communication.azure.com/;accesskey=ZmFrZWtleQ=="
)
_FAKE_SENDER = "DoNotReply@example.azurecomm.net"


@pytest.fixture()
def sender() -> EmailSender:
    with patch(
        "news_scout.email_sender.EmailClient.from_connection_string"
    ) as mock_factory:
        mock_factory.return_value = MagicMock()
        s = EmailSender(_FAKE_CONN_STR, _FAKE_SENDER)
    return s


class TestBuildBody:
    def test_plain_text_contains_topic(self, sender):
        plain, _ = sender._build_body(
            {"AI News": "## AI\n\nBig developments."}, "2024-01-15"
        )
        assert "AI News" in plain
        assert "2024-01-15" in plain

    def test_html_contains_markup(self, sender):
        _, html = sender._build_body({"Climate": "## Climate\n\nRising seas."}, "2024-06-01")
        assert "<html" in html
        assert "Climate" in html

    def test_multiple_topics_all_present(self, sender):
        reports = {
            "Topic A": "Content A",
            "Topic B": "Content B",
        }
        plain, html = sender._build_body(reports, "2024-03-10")
        for name in ("Topic A", "Topic B", "Content A", "Content B"):
            assert name in plain
            assert name in html


class TestSendReport:
    def _make_sender_with_mock_client(self) -> tuple[EmailSender, MagicMock]:
        mock_client = MagicMock()
        with patch(
            "news_scout.email_sender.EmailClient.from_connection_string",
            return_value=mock_client,
        ):
            s = EmailSender(_FAKE_CONN_STR, _FAKE_SENDER)
        return s, mock_client

    def test_send_calls_acs_begin_send(self):
        sender, mock_client = self._make_sender_with_mock_client()
        mock_client.begin_send.return_value.result.return_value = {"id": "msg-123"}

        sender.send_report(
            "recipient@example.com",
            {"Tech": "Some tech news."},
            datetime(2024, 1, 15),
        )

        mock_client.begin_send.assert_called_once()
        call_kwargs = mock_client.begin_send.call_args[0][0]
        assert call_kwargs["senderAddress"] == _FAKE_SENDER
        assert call_kwargs["recipients"]["to"][0]["address"] == "recipient@example.com"

    def test_subject_includes_date(self):
        sender, mock_client = self._make_sender_with_mock_client()
        mock_client.begin_send.return_value.result.return_value = {"id": "msg-456"}

        sender.send_report(
            "r@example.com",
            {"News": "content"},
            datetime(2024, 7, 4),
        )

        call_kwargs = mock_client.begin_send.call_args[0][0]
        assert "2024-07-04" in call_kwargs["content"]["subject"]

    def test_both_plain_and_html_content_sent(self):
        sender, mock_client = self._make_sender_with_mock_client()
        mock_client.begin_send.return_value.result.return_value = {"id": "msg-789"}

        sender.send_report(
            "r@example.com",
            {"Topic": "Report content."},
            datetime(2024, 3, 1),
        )

        call_kwargs = mock_client.begin_send.call_args[0][0]
        assert "Topic" in call_kwargs["content"]["plainText"]
        assert "<html" in call_kwargs["content"]["html"]
