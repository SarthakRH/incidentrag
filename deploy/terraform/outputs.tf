output "api_repository_url" {
  value = aws_ecr_repository.api.repository_url
}

output "ui_repository_url" {
  value = aws_ecr_repository.ui.repository_url
}

output "application_secret_arn" {
  value = aws_secretsmanager_secret.application.arn
}
