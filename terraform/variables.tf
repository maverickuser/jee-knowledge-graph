variable "aws_region" {
  description = "AWS region for knowledge graph write-path resources."
  type        = string
  default     = "ap-south-1"
}

variable "project_name" {
  description = "Base name used to prefix knowledge graph resources."
  type        = string
  default     = "jee-knowledge-graph"
}

variable "graph_table_name" {
  description = "DynamoDB table name for versioned knowledge graph items."
  type        = string
  default     = "jee-knowledge-graph"
}

variable "artifact_bucket_name" {
  description = "Optional explicit S3 bucket name for graph import artifacts. Leave empty to derive one from project_name and account."
  type        = string
  default     = ""
}

variable "environment" {
  description = "Deployment environment name, for example dev, staging, or prod."
  type        = string
  default     = "dev"
}

variable "deletion_protection_enabled" {
  description = "Enable DynamoDB deletion protection. Defaults to true outside dev when null."
  type        = bool
  default     = null
}

variable "import_report_retention_days" {
  description = "Days to retain graph import reports in S3."
  type        = number
  default     = 90
}

