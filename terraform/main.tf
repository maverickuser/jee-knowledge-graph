data "aws_caller_identity" "current" {}

locals {
  artifact_bucket_name        = var.artifact_bucket_name != "" ? var.artifact_bucket_name : "${var.project_name}-${data.aws_caller_identity.current.account_id}-graph-artifacts"
  deletion_protection_enabled = var.deletion_protection_enabled == null ? var.environment != "dev" : var.deletion_protection_enabled
}

resource "aws_dynamodb_table" "knowledge_graph" {
  name                        = var.graph_table_name
  billing_mode                = "PAY_PER_REQUEST"
  hash_key                    = "PK"
  range_key                   = "SK"
  deletion_protection_enabled = local.deletion_protection_enabled

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Service     = "knowledge-graph-write-path"
  }
}

resource "aws_s3_bucket" "graph_artifacts" {
  bucket = local.artifact_bucket_name

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Service     = "knowledge-graph-import-artifacts"
  }
}

resource "aws_s3_bucket_versioning" "graph_artifacts" {
  bucket = aws_s3_bucket.graph_artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "graph_artifacts" {
  bucket = aws_s3_bucket.graph_artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "graph_artifacts" {
  bucket = aws_s3_bucket.graph_artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "graph_artifacts" {
  bucket = aws_s3_bucket.graph_artifacts.id

  rule {
    id     = "expire-import-reports"
    status = "Enabled"

    filter {
      prefix = "graph-import-reports/"
    }

    expiration {
      days = var.import_report_retention_days
    }
  }
}

resource "aws_iam_role" "graph_writer" {
  name = "${var.project_name}-graph-writer"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = var.project_name
    Environment = var.environment
    Service     = "knowledge-graph-writer"
  }
}

resource "aws_iam_role_policy" "graph_writer" {
  name = "${var.project_name}-graph-writer-policy"
  role = aws_iam_role.graph_writer.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "WriteKnowledgeGraphTable"
        Effect = "Allow"
        Action = [
          "dynamodb:BatchWriteItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem",
          "dynamodb:UpdateItem",
          "dynamodb:DescribeTable",
          "dynamodb:Query",
          "dynamodb:GetItem",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.knowledge_graph.arn
      },
      {
        Sid    = "ReadWriteGraphArtifacts"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.graph_artifacts.arn}/*"
      },
      {
        Sid      = "ListGraphArtifactBucket"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.graph_artifacts.arn
      }
    ]
  })
}
