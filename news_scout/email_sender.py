"""Email sender for the daily news scout report."""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown as md

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
    """Sends the daily news report via SMTP."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def send_report(
        self,
        recipient: str,
        reports: dict[str, str],
        date: datetime | None = None,
    ) -> None:
        """Compose and send the daily report email.

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

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.username
        msg["To"] = recipient
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(self.username, self.password)
            server.sendmail(self.username, [recipient], msg.as_string())

        logger.info("Report email sent to %s", recipient)

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
