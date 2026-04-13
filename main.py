"""Entry point for the Daily News Scout.

Environment variables (set in .env locally or as GitHub Secrets in CI):
  OPENAI_API_KEY         – required
  EMAIL_TO               – required
  ACS_CONNECTION_STRING  – required (Azure Communication Services connection string)
  ACS_SENDER_ADDRESS     – required (verified sender, e.g. DoNotReply@<domain>.azurecomm.net)
  OPENAI_MODEL           – default: gpt-4o
  TOPICS_CONFIG          – path to topics YAML, default: config/topics.yaml
"""

import logging
import os
import sys

import yaml
from dotenv import load_dotenv
from openai import OpenAI

from news_scout.agent import NewsScoutAgent
from news_scout.email_sender import EmailSender

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        logger.error("Required environment variable %s is not set.", name)
        sys.exit(1)
    return value


def load_topics(config_path: str = "config/topics.yaml") -> list[dict]:
    with open(config_path, "r", encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    return cfg.get("topics", [])


def main() -> None:
    openai_api_key = _require_env("OPENAI_API_KEY")
    email_to = _require_env("EMAIL_TO")
    acs_connection_string = _require_env("ACS_CONNECTION_STRING")
    acs_sender_address = _require_env("ACS_SENDER_ADDRESS")
    model = os.environ.get("OPENAI_MODEL", "gpt-4o")
    topics_path = os.environ.get("TOPICS_CONFIG", "config/topics.yaml")

    topics = load_topics(topics_path)
    if not topics:
        logger.error("No topics found in %s", topics_path)
        sys.exit(1)

    logger.info(
        "Loaded %d topic(s): %s", len(topics), [t.get("name") for t in topics]
    )

    client = OpenAI(api_key=openai_api_key)
    agent = NewsScoutAgent(client, model=model)

    reports: dict[str, str] = {}
    for topic in topics:
        topic_name = topic.get("name", "Unknown")
        try:
            report, _ = agent.scout_topic(topic)
            reports[topic_name] = report
            logger.info("Report ready for: %s", topic_name)
        except Exception as exc:
            logger.error("Failed to scout '%s': %s", topic_name, exc)
            reports[topic_name] = f"*Error generating report: {exc}*\n"

    sender = EmailSender(acs_connection_string, acs_sender_address)
    sender.send_report(email_to, reports)
    logger.info("All done.")


if __name__ == "__main__":
    main()
