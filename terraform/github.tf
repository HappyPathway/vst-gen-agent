# ---------------------------------------------------------------------------
# GitHub provider — manages Actions secrets, variables, and the OAuth App
# client ID for the vst-gen-agent repository.
#
# Required variable:
#   TF_VAR_github_token — fine-grained PAT or classic PAT with:
#     - repo:  Actions secrets + variables (read/write)
#     - admin:repo_hook (if webhook management is needed in future)
#
# GitHub OAuth App:
#   Terraform cannot create OAuth Apps — create it once in the GitHub UI:
#     https://github.com/organizations/HappyPathway/settings/applications
#     (or https://github.com/settings/developers for personal accounts)
#   Settings:
#     Application name:  VST Gen Registry
#     Homepage URL:      <registry_url output from `terraform output`>
#     Authorization callback URL: (leave blank — device flow doesn't need one)
#   After creation, copy the Client ID and pass it as:
#     TF_VAR_github_oauth_client_id=<client_id>
#   No client secret is needed — GitHub device flow uses public clients.
# ---------------------------------------------------------------------------

provider "github" {
  token = var.github_token
  owner = var.github_owner
}

# ---------------------------------------------------------------------------
# Actions secrets — sensitive values; encrypted at rest by GitHub
# ---------------------------------------------------------------------------

# GCP Workload Identity provider for keyless auth (deploy-registry.yml)
resource "github_actions_secret" "gcp_workload_identity_provider" {
  repository      = var.github_agent_repo
  secret_name     = "GCP_WORKLOAD_IDENTITY_PROVIDER"
  plaintext_value = google_iam_workload_identity_pool_provider.github.name
}

# GCP service account email for keyless auth (deploy-registry.yml)
resource "github_actions_secret" "gcp_service_account" {
  repository      = var.github_agent_repo
  secret_name     = "GCP_SERVICE_ACCOUNT"
  plaintext_value = google_service_account.github_deploy.email
}

# Registry API base URL (revalidate.yml, registry-health.yml, update-device-index.yml,
# update-readme-stats.yml). Stored as a secret so it stays out of public logs.
resource "github_actions_secret" "registry_url" {
  repository      = var.github_agent_repo
  secret_name     = "REGISTRY_URL"
  plaintext_value = google_cloud_run_v2_service.registry_api.uri
}

# API key used by the revalidate workflow to call POST /admin/revalidate.
# This is the same key passed to Cloud Scheduler — one key, two callers.
resource "github_actions_secret" "registry_api_key" {
  repository      = var.github_agent_repo
  secret_name     = "REGISTRY_API_KEY"
  plaintext_value = var.revalidation_api_key
}

# ---------------------------------------------------------------------------
# Actions variables — non-sensitive; visible in workflow logs
# ---------------------------------------------------------------------------

# GitHub OAuth App client ID distributed to CLI users via registry_client.py.
# Not sensitive — it is a public identifier; only the device flow uses it.
resource "github_actions_variable" "github_oauth_client_id" {
  repository    = var.github_agent_repo
  variable_name = "GITHUB_OAUTH_CLIENT_ID"
  value         = var.github_oauth_client_id
}
