output "registry_url" {
  description = "Base URL of the VST Gen Device Registry API."
  value       = google_cloud_run_v2_service.registry_api.uri
}

output "docker_image_repo" {
  description = "Artifact Registry repo for the registry API Docker image."
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project}/vst-gen/registry-api"
}

output "workload_identity_provider" {
  description = "Full resource name of the WIF provider — value for GCP_WORKLOAD_IDENTITY_PROVIDER in GitHub Actions (managed automatically as an Actions secret)."
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "deploy_service_account" {
  description = "Email of the GitHub Actions deploy service account — value for GCP_SERVICE_ACCOUNT in GitHub Actions (managed automatically as an Actions secret)."
  value       = google_service_account.github_deploy.email
}
