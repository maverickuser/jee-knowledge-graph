output "graph_table_name" {
  value = aws_dynamodb_table.knowledge_graph.name
}

output "graph_table_arn" {
  value = aws_dynamodb_table.knowledge_graph.arn
}

output "graph_artifact_bucket_name" {
  value = aws_s3_bucket.graph_artifacts.bucket
}

output "graph_writer_role_arn" {
  value = aws_iam_role.graph_writer.arn
}

