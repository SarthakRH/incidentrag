variable "aws_region" {
  type        = string
  description = "AWS region for IncidentRAG resources"
  default     = "us-east-1"
}

variable "name" {
  type        = string
  description = "Resource name prefix"
  default     = "incidentrag"
}

variable "environment" {
  type        = string
  description = "Deployment environment"
  default     = "staging"
}
