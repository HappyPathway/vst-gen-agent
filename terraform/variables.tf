variable "gcp_project" {
  description = "GCP project ID."
  type        = string
  default     = "happypathway-1522441039906"
}

variable "gcp_region" {
  description = "Cloud Run region + Artifact Registry location."
  type        = string
  default     = "us-central1"
}

variable "revalidation_api_key" {
  description = "API key used by Cloud Scheduler and the revalidate GitHub Actions workflow to call POST /admin/revalidate. Register with `registry_client.py login` and pass via TF_VAR_revalidation_api_key."
  type        = string
  sensitive   = true
}

# ---------------------------------------------------------------------------
# GitHub provider variables
# ---------------------------------------------------------------------------

variable "github_token" {
  description = "GitHub fine-grained PAT (or classic PAT) with 'repo' scope on vst-gen-agent. Used by Terraform to manage Actions secrets and variables. Pass via TF_VAR_github_token."
  type        = string
  sensitive   = true
}

variable "github_owner" {
  description = "GitHub organization or user that owns the vst-gen-agent repository."
  type        = string
  default     = "HappyPathway"
}

variable "github_agent_repo" {
  description = "Name of the vst-gen-agent GitHub repository (without owner prefix)."
  type        = string
  default     = "vst-gen-agent"
}

variable "github_oauth_client_id" {
  description = <<-EOT
    Client ID of the GitHub OAuth App used for the device flow login.
    Not sensitive — it is a public identifier distributed to CLI users.

    Create the app once at:
      https://github.com/organizations/<org>/settings/applications
    or for personal accounts:
      https://github.com/settings/developers

    Required settings:
      Application name:              VST Gen Registry
      Homepage URL:                  <registry_url output>
      Authorization callback URL:    (leave blank)
    No client secret is needed for the device flow.

    Pass via: TF_VAR_github_oauth_client_id=<client_id>
  EOT
  type        = string
  default     = ""
}

