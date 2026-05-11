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
  description = "API key used by Cloud Scheduler to call POST /admin/revalidate. Register with `registry_client.py login` and pass via TF_VAR_revalidation_api_key."
  type        = string
  sensitive   = true
}
