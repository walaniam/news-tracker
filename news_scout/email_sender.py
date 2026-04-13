"""Email sender for the daily news scout report (Azure Communication Services)."""

import logging
from datetime import datetime, timezone

import markdown as md
from azure.communication.email import EmailClient

logger = logging.getLogger(__name__)

_EMAIL_STYLES = """
body {
    font-family: Arial, Helvetica, sans-serif;
    max-width: 820px;
    margin: 0 auto;
    padding: 24px;
    color: #222;
    line-height: 1.6;
}
h1 { color: #1a1a2e; border-bottom: 2px solid #16213e; padding-bottom: 8px; }
h2 { color: #16213e; border-bottom: 1px solid #ddd; padding-bottom: 4px; margin-top: 32px; }
h3 { color: #0f3460; }
ul  { padding-left: 22px; }
li  { margin-bottom: 6px; }
a   { color: #0f3460; }
hr  { border: none; border-top: 1px solid #ddd; margin: 24px 0; }
pre { background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; }
code { background: #f0f0f0; padding: 2px 4px; border-radius: 3px; }
"""


class EmailSender:
    """Sends the daily news report via Azure Communication Services (ACS)."""

    def __init__(self, connection_string: str, sender_address: str):
        """
        Args:
            connection_string: ACS resource connection string.
            sender_address:    Verified sender email address configured in ACS
                               (e.g. ``DoNotReply@<domain>.azurecomm.net``).
        """
        self.sender_address = sender_address
        self._client = EmailClient.from_connection_string(connection_string)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_report(
        self,
        recipient: str,
        reports: dict[str, str],
        date: datetime | None = None,
    ) -> None:
        """Compose and send the daily report email via ACS.

        Args:
            recipient: destination email address.
            reports:   mapping of topic name → Markdown report text.
            date:      report date (defaults to today UTC).
        """
        if date is None:
            date = datetime.now(timezone.utc)

        date_str = date.strftime("%Y-%m-%d")
        subject = f"Daily News Scout Report – {date_str}"

        plain, html = self._build_body(reports, date_str)

        message = {
            "senderAddress": self.sender_address,
            "recipients": {"to": [{"address": recipient}]},
            "content": {
                "subject": subject,
                "plainText": plain,
                "html": html,
            },
        }

        poller = self._client.begin_send(message)
        result = poller.result()
        logger.info(
            "Report email sent to %s via ACS (message id: %s)",
            recipient,
            result.get("id", "unknown"),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_body(
        reports: dict[str, str], date_str: str
    ) -> tuple[str, str]:
        """Return (plain_text, html) for the combined report."""
        combined_md = (
            f"# Daily News Scout Report\n\n**Date:** {date_str}\n\n---\n\n"
        )
        for topic_name, report_text in reports.items():
            combined_md += f"## Topic: {topic_name}\n\n{report_text}\n\n---\n\n"

        html_body = md.markdown(combined_md, extensions=["extra", "sane_lists"])
        html = (
            "<!DOCTYPE html>\n"
            "<html lang='en'>\n"
            "<head>\n"
            "  <meta charset='utf-8'>\n"
            "  <meta name='viewport' content='width=device-width, initial-scale=1'>\n"
            f"  <style>{_EMAIL_STYLES}</style>\n"
            "</head>\n"
            f"<body>{html_body}</body>\n"
            "</html>"
        )
        return combined_md, html
