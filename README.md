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

#### Prerequisites

- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli) installed and logged in (`az login`)
- The `communication` CLI extension (installed automatically by the commands below if missing)

#### Azure CLI setup (recommended)

Run the following commands once. Replace the placeholder values (`<…>`) with your own names.

```bash
# Variables – change these to your preferred names/region
RESOURCE_GROUP="news-tracker-rg"
LOCATION="eastus"                        # az account list-locations -o table
ACS_NAME="news-tracker-acs"
EMAIL_SERVICE_NAME="news-tracker-email"

# 1. Create a resource group (skip if you already have one)
az group create --name "$RESOURCE_GROUP" --location "$LOCATION"

# 2. Create the ACS resource
az communication create \
  --name "$ACS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "Global" \
  --data-location "United States"

# 3. Create the Email Communication Service
az communication email create \
  --name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "Global" \
  --data-location "United States"

# 4. Provision the free Azure-managed domain (no DNS changes required)
az communication email domain create \
  --name "AzureManagedDomain" \
  --email-service-name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "Global" \
  --domain-management AzureManaged

# 5. Retrieve the full domain resource ID
DOMAIN_ID=$(az communication email domain show \
  --name "AzureManagedDomain" \
  --email-service-name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id --output tsv)

# 6. Link the email domain to the ACS resource
az communication update \
  --name "$ACS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --linked-domains "[$DOMAIN_ID]"

# 7. Retrieve the connection string (store this as ACS_CONNECTION_STRING)
az communication list-key \
  --name "$ACS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query primaryConnectionString --output tsv

# 8. Retrieve the sender address (store this as ACS_SENDER_ADDRESS)
az communication email domain show \
  --name "AzureManagedDomain" \
  --email-service-name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "mailFromSenderDomain" --output tsv | \
  awk '{print "DoNotReply@" $1}'
```

> **Tip:** Steps 7 and 8 print the two values you need as GitHub secrets in the next step.

#### Azure Portal setup (optional alternative)

If you prefer a graphical interface:

1. In the [Azure Portal](https://portal.azure.com), create an **Azure Communication Services** resource.
2. Inside that resource, add an **Email Communication Service** and provision the free `*.azurecomm.net` domain (no DNS changes needed).
3. Link the domain to your ACS resource (**Try email → Connect domain**).
4. Copy the **Connection string** from the ACS resource's **Keys** blade.
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
