"""Tests for EmailSender."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from news_scout.email_sender import EmailSender


@pytest.fixture()
def sender() -> EmailSender:
    return EmailSender("smtp.gmail.com", 587, "sender@example.com", "secret")


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
    def test_send_calls_smtp_correctly(self, sender):
        mock_server = MagicMock()

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            sender.send_report(
                "recipient@example.com",
                {"Tech": "Some tech news."},
                datetime(2024, 1, 15),
            )

        mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("sender@example.com", "secret")
        mock_server.sendmail.assert_called_once()
        # Verify recipient address
        _, call_args, _ = mock_server.sendmail.mock_calls[0]
        assert call_args[1] == ["recipient@example.com"]

    def test_subject_includes_date(self, sender):
        mock_server = MagicMock()
        captured: list[str] = []

        def capture_sendmail(from_addr, to_addrs, msg_str):
            captured.append(msg_str)

        mock_server.sendmail.side_effect = capture_sendmail

        with patch("smtplib.SMTP") as mock_smtp_cls:
            mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            sender.send_report(
                "r@example.com",
                {"News": "content"},
                datetime(2024, 7, 4),
            )

        assert captured, "sendmail was not called"
        assert "2024-07-04" in captured[0]
