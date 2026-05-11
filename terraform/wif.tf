# ---------------------------------------------------------------------------
# Workload Identity Federation — GitHub Actions → GCP (no long-lived keys)
#
# GitHub Actions OIDC tokens are exchanged for short-lived GCP credentials.
# Only tokens originating from the vst-gen-agent master branch can
# impersonate the deploy service account.
# ---------------------------------------------------------------------------

resource "google_project_service" "iam_credentials" {
  service            = "iamcredentials.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam" {
  service            = "iam.googleapis.com"
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# WIF Pool + GitHub OIDC Provider
# ---------------------------------------------------------------------------

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.gcp_project
  workload_identity_pool_id = "vst-gen-github"
  display_name              = "VST Gen — GitHub Actions"
  description               = "OIDC federation for HappyPathway/vst-gen-agent workflows"

  depends_on = [google_project_service.iam_credentials]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  project                            = var.gcp_project
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-actions"
  display_name                       = "GitHub Actions OIDC"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  # Scope to the vst-gen-agent repo on the master branch only.
  attribute_condition = <<-EOT
    assertion.repository == "${var.github_owner}/${var.github_agent_repo}"
    && assertion.ref == "refs/heads/master"
  EOT
}

# ---------------------------------------------------------------------------
# Deploy service account — used by GitHub Actions to push images + deploy
# ---------------------------------------------------------------------------

resource "google_service_account" "github_deploy" {
  project      = var.gcp_project
  account_id   = "vst-gen-github-deploy"
  display_name = "VST Gen — GitHub Actions deploy"
}

# Push images to Artifact Registry
resource "google_project_iam_member" "github_deploy_ar_writer" {
  project = var.gcp_project
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

# Deploy new Cloud Run revisions
resource "google_project_iam_member" "github_deploy_run_admin" {
  project = var.gcp_project
  role    = "roles/run.admin"
  member  = "serviceAccount:${google_service_account.github_deploy.email}"
}

# Allow the deploy SA to act as the Cloud Run SA (needed for --service-account flag)
resource "google_service_account_iam_member" "github_deploy_act_as_registry_sa" {
  service_account_id = google_service_account.registry_api.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.github_deploy.email}"
}

# ---------------------------------------------------------------------------
# Allow the WIF identity (repo-scoped) to impersonate the deploy SA
# ---------------------------------------------------------------------------

resource "google_service_account_iam_member" "github_wif_impersonate" {
  service_account_id = google_service_account.github_deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_owner}/${var.github_agent_repo}"
}
