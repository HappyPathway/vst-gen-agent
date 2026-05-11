terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
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
# GCS — device registry bucket (panel images, JSON exports)
# ---------------------------------------------------------------------------

resource "google_storage_bucket" "registry" {
  name                        = var.registry_bucket
  project                     = var.gcp_project
  location                    = "US"
  uniform_bucket_level_access = true
  force_destroy               = false

  cors {
    origin          = ["*"]
    method          = ["GET", "HEAD"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }
}

# Public read on the panels/ prefix
resource "google_storage_bucket_iam_member" "public_panels_read" {
  bucket = google_storage_bucket.registry.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"

  condition {
    title      = "panels-prefix-only"
    expression = "resource.name.startsWith(\"${var.registry_bucket}/panels/\")"
  }
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

# GCS objectAdmin on the registry bucket only
resource "google_storage_bucket_iam_member" "registry_gcs" {
  bucket = google_storage_bucket.registry.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.registry_api.email}"
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

      env {
        name  = "REGISTRY_BUCKET"
        value = var.registry_bucket
      }

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
