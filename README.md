# News Tracker – AI-Powered Daily News Scout

An AI agent that scouts up to 10 globally diverse news portals for your configured topics and
sends you a concise, synthesised daily email report.

---

## Features

| Requirement | How it is met |
|---|---|
| Scans up to 10 portals per topic | The LLM picks portals at runtime; the agent fetches their RSS feeds |
| Portals chosen by AI, not hardcoded | GPT-4o selects sources based on topic context |
| Global sources (not only Western media) | The prompt explicitly asks for regional and local outlets |
| Easily configurable topics | Edit `config/topics.yaml` – no code changes needed |
| Daily email with summary / trends | `EmailSender` composes an HTML + plain-text email every day |
| GitHub Actions automation | `.github/workflows/news_scout.yml` – scheduled at 08:00 UTC |
| Simple deployment | Fork → set four secrets → done |

---

## Repository layout

```
news-tracker/
├── .github/workflows/news_scout.yml   # Daily automation
├── config/
│   └── topics.yaml                    # ← Edit this to change topics
├── news_scout/
│   ├── agent.py                       # LLM-driven scouting agent
│   └── email_sender.py                # ACS email sender
├── tests/
│   ├── test_agent.py
│   └── test_email_sender.py
├── main.py                            # Entry point
├── requirements.txt
└── .env.example
```

---

## Quick-start: GitHub Actions (recommended)

### 1. Fork this repository

Click **Fork** at the top-right of the GitHub page.

### 2. Configure topics

Edit `config/topics.yaml` in your fork:

```yaml
topics:
  - name: "Middle East Conflict"
    description: >
      Ongoing conflicts, diplomacy, and humanitarian situations
      in the Middle East.

  - name: "Artificial Intelligence"
    description: >
      AI breakthroughs, regulation, safety, and societal impact.
```

Commit and push the change.

### 3. Set up Azure Communication Services (Email)

This project uses **Azure Communication Services (ACS)** for reliable, no-SMTP email delivery.

1. In the [Azure Portal](https://portal.azure.com), create an **Azure Communication Services** resource.
2. Inside that resource, add an **Email Communication Service** and provision a domain
   (the free `*.azurecomm.net` domain works with no DNS changes).
3. Link the Email Communication Service domain to your ACS resource
   (**Try email → Connect domain**).
4. From the ACS resource's **Keys** blade, copy the **Connection string**.
5. Note the sender address shown in the portal (e.g. `DoNotReply@<subdomain>.azurecomm.net`).

### 4. Set repository secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret name | Description |
|---|---|
| `OPENAI_API_KEY` | Your OpenAI API key |
| `EMAIL_TO` | Recipient e-mail address |
| `ACS_CONNECTION_STRING` | ACS resource connection string (from the Keys blade) |
| `ACS_SENDER_ADDRESS` | Verified sender address (e.g. `DoNotReply@<subdomain>.azurecomm.net`) |

#### Optional repository variable

| Variable name | Default | Description |
|---|---|---|
| `OPENAI_MODEL` | `gpt-4o` | Override the OpenAI model (e.g. `gpt-4o-mini` to reduce cost) |

Set this under **Settings → Secrets and variables → Actions → Variables**.

### 5. Enable the workflow

The workflow runs automatically at **08:00 UTC** every day.  
To trigger it immediately: **Actions → Daily News Scout → Run workflow**.

---

## Local development

```bash
# 1. Clone and create a virtual environment
git clone https://github.com/<you>/news-tracker.git
cd news-tracker
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Edit .env with your ACS connection string, sender address, and OpenAI key

# 4. Run
python main.py
```

### Run tests

```bash
pytest tests/ -v
```

---

## How it works

```
For each topic in config/topics.yaml
  │
  ├─ [LLM] Identify up to 10 globally diverse news portals
  │         (includes regional sources relevant to the topic)
  │
  ├─ [HTTP] Fetch articles from each portal
  │         └─ Try RSS feed  →  auto-discover RSS  →  scrape headlines
  │
  └─ [LLM] Generate a Markdown report with:
            • Executive Summary
            • Key Developments
            • Trends & Analysis
            • Regional Perspectives
            • Notable Sources & Links
│
└─ [ACS]  Send combined HTML email via Azure Communication Services
```

---

## Environment variables reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | – | OpenAI API key |
| `EMAIL_TO` | ✅ | – | Report recipient |
| `ACS_CONNECTION_STRING` | ✅ | – | ACS resource connection string |
| `ACS_SENDER_ADDRESS` | ✅ | – | Verified ACS sender address |
| `OPENAI_MODEL` | ❌ | `gpt-4o` | OpenAI model to use |
| `TOPICS_CONFIG` | ❌ | `config/topics.yaml` | Path to topics file |

---

## License

[MIT](LICENSE)
