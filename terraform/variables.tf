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

variable "registry_bucket" {
  description = "GCS bucket name for the device registry (panel images, JSON exports)."
  type        = string
  default     = "vst-gen-device-registry"
}
