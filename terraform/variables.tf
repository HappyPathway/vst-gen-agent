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
