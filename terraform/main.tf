terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    github = {
      source  = "integrations/github"
      version = "~> 6.0"
    }
  }

  # State can share the same GCS state bucket as iron-static.
  # Copy gcs.tfbackend.example → gcs.tfbackend with:
  #   bucket = "<your-state-bucket>"
  #   prefix = "vst-gen-registry"
  backend "gcs" {}
}

provider "google" {
  project = var.gcp_project
  region  = var.gcp_region
}

# ---------------------------------------------------------------------------
# Required APIs
# ---------------------------------------------------------------------------

resource "google_project_service" "run" {
  service            = "run.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "artifact_registry" {
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "firestore" {
  service            = "firestore.googleapis.com"
  disable_on_destroy = false
}

# ---------------------------------------------------------------------------
# Artifact Registry — Docker repo for Cloud Run image
# ---------------------------------------------------------------------------

resource "google_artifact_registry_repository" "vst_gen" {
  project       = var.gcp_project
  location      = var.gcp_region
  repository_id = "vst-gen"
  format        = "DOCKER"

  depends_on = [google_project_service.artifact_registry]
}

# ---------------------------------------------------------------------------
# Service account for Cloud Run
# ---------------------------------------------------------------------------

resource "google_service_account" "registry_api" {
  account_id   = "vst-gen-registry-api"
  display_name = "VST Gen Device Registry — Cloud Run"
  project      = var.gcp_project
}

# Firestore read/write
resource "google_project_iam_member" "registry_firestore" {
  project = var.gcp_project
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.registry_api.email}"
}

# ---------------------------------------------------------------------------
# Cloud Run — VST Gen Device Registry API
# ---------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "registry_api" {
  name     = "vst-gen-registry"
  location = var.gcp_region
  project  = var.gcp_project

  template {
    service_account = google_service_account.registry_api.email

    containers {
      # Image is built and pushed separately via Cloud Build / GitHub Actions.
      # On first apply, push a placeholder or the real image before applying.
      image = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project}/vst-gen/registry-api:latest"

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
  }

  depends_on = [
    google_project_service.run,
    google_artifact_registry_repository.vst_gen,
  ]
}

# Allow unauthenticated invocations (API uses its own X-API-Key auth)
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  project  = var.gcp_project
  location = var.gcp_region
  name     = google_cloud_run_v2_service.registry_api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ---------------------------------------------------------------------------
# Cloud Scheduler — periodic revalidation of indexed repos
# ---------------------------------------------------------------------------

resource "google_project_service" "scheduler" {
  service            = "cloudscheduler.googleapis.com"
  disable_on_destroy = false
}

# Dedicated SA that Cloud Scheduler uses to call the revalidate endpoint.
# It gets an API key at bootstrap time (store in Secret Manager or as a
# Cloud Run env var REVALIDATION_API_KEY).
resource "google_service_account" "scheduler" {
  account_id   = "vst-gen-scheduler"
  display_name = "VST Gen Registry — Cloud Scheduler invoker"
  project      = var.gcp_project
}

resource "google_cloud_run_v2_service_iam_member" "scheduler_invoker" {
  project  = var.gcp_project
  location = var.gcp_region
  name     = google_cloud_run_v2_service.registry_api.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "revalidate" {
  name        = "vst-gen-revalidate"
  description = "Re-check all indexed GitHub repos for continued public visibility"
  schedule    = "0 3 * * *" # 03:00 UTC daily
  time_zone   = "UTC"
  region      = var.gcp_region
  project     = var.gcp_project

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.registry_api.uri}/admin/revalidate"

    headers = {
      "X-API-Key" = var.revalidation_api_key
    }

    oidc_token {
      service_account_email = google_service_account.scheduler.email
      audience              = google_cloud_run_v2_service.registry_api.uri
    }
  }

  depends_on = [
    google_project_service.scheduler,
    google_cloud_run_v2_service_iam_member.scheduler_invoker,
  ]
}
