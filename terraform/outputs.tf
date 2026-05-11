output "registry_url" {
  description = "Base URL of the VST Gen Device Registry API."
  value       = google_cloud_run_v2_service.registry_api.uri
}

output "docker_image_repo" {
  description = "Artifact Registry repo for the registry API Docker image."
  value       = "${var.gcp_region}-docker.pkg.dev/${var.gcp_project}/vst-gen/registry-api"
}
