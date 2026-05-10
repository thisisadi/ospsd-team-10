variable "aws_region" {
  description = "AWS region for App Runner and ECR."
  type        = string
  default     = "us-east-1"
}

variable "service_name" {
  description = "App Runner service name."
  type        = string
  default     = "ospsd-team-10-hw3"
}

variable "image_identifier" {
  description = "Fully qualified ECR image URI, including tag."
  type        = string
}

variable "storage_provider" {
  description = "Storage provider selected at runtime: s3, gcp, or mock."
  type        = string
  default     = "s3"

  validation {
    condition     = contains(["s3", "gcp", "mock"], var.storage_provider)
    error_message = "storage_provider must be one of: s3, gcp, mock."
  }
}
