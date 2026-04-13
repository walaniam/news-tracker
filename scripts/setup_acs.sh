#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup_acs.sh – Provision Azure Communication Services for news-tracker
#
# Usage:
#   bash scripts/setup_acs.sh
#
# Configurable via environment variables (all have sensible defaults):
#
#   RESOURCE_GROUP      Azure resource group name    (default: news-tracker-rg)
#   LOCATION            Azure region for the group   (default: eastus)
#   ACS_NAME            ACS resource name            (default: news-tracker-acs)
#   EMAIL_SERVICE_NAME  Email Communication Service  (default: news-tracker-email)
#
# On success the script prints the two values you need as GitHub secrets:
#   ACS_CONNECTION_STRING
#   ACS_SENDER_ADDRESS
#
# Prerequisites:
#   - Azure CLI installed  https://learn.microsoft.com/cli/azure/install-azure-cli
#   - Logged in:  az login
# ---------------------------------------------------------------------------
set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration – override any of these with environment variables
# ---------------------------------------------------------------------------
RESOURCE_GROUP="${RESOURCE_GROUP:-news-tracker-rg}"
LOCATION="${LOCATION:-eastus}"
ACS_NAME="${ACS_NAME:-news-tracker-acs}"
EMAIL_SERVICE_NAME="${EMAIL_SERVICE_NAME:-news-tracker-email}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo "[INFO]  $*"; }
error() { echo "[ERROR] $*" >&2; exit 1; }

command -v az &>/dev/null || error "Azure CLI not found. Install it from https://learn.microsoft.com/cli/azure/install-azure-cli"

# Ensure the communication extension is available
if ! az extension show --name communication &>/dev/null; then
  info "Installing Azure CLI 'communication' extension..."
  az extension add --name communication --yes
fi

# ---------------------------------------------------------------------------
# 1. Resource group
# ---------------------------------------------------------------------------
info "Creating resource group '$RESOURCE_GROUP' in '$LOCATION'..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# ---------------------------------------------------------------------------
# 2. Azure Communication Services resource
# ---------------------------------------------------------------------------
info "Creating ACS resource '$ACS_NAME'..."
az communication create \
  --name "$ACS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "Global" \
  --data-location "United States" \
  --output none

# ---------------------------------------------------------------------------
# 3. Email Communication Service
# ---------------------------------------------------------------------------
info "Creating Email Communication Service '$EMAIL_SERVICE_NAME'..."
az communication email create \
  --name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "Global" \
  --data-location "United States" \
  --output none

# ---------------------------------------------------------------------------
# 4. Azure-managed domain (free, no DNS changes required)
# ---------------------------------------------------------------------------
info "Provisioning Azure-managed email domain..."
az communication email domain create \
  --name "AzureManagedDomain" \
  --email-service-name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --location "Global" \
  --domain-management AzureManaged \
  --output none

# ---------------------------------------------------------------------------
# 5. Link the email domain to the ACS resource
# ---------------------------------------------------------------------------
info "Retrieving domain resource ID..."
DOMAIN_ID=$(az communication email domain show \
  --name "AzureManagedDomain" \
  --email-service-name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query id --output tsv)

info "Linking email domain to ACS resource..."
az communication update \
  --name "$ACS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --linked-domains "[$DOMAIN_ID]" \
  --output none

# ---------------------------------------------------------------------------
# 6. Retrieve secrets and print them
# ---------------------------------------------------------------------------
info "Retrieving connection string..."
ACS_CONNECTION_STRING=$(az communication list-key \
  --name "$ACS_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query primaryConnectionString --output tsv)

info "Retrieving sender address..."
MAIL_DOMAIN=$(az communication email domain show \
  --name "AzureManagedDomain" \
  --email-service-name "$EMAIL_SERVICE_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query "mailFromSenderDomain" --output tsv)
ACS_SENDER_ADDRESS="DoNotReply@${MAIL_DOMAIN}"

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
echo ""
echo "================================================================"
echo "  ACS setup complete. Add the following GitHub Actions secrets:"
echo "================================================================"
echo ""
echo "  ACS_CONNECTION_STRING=${ACS_CONNECTION_STRING}"
echo "  ACS_SENDER_ADDRESS=${ACS_SENDER_ADDRESS}"
echo ""
echo "  Go to: Settings → Secrets and variables → Actions → New repository secret"
echo "================================================================"
