locals {
  prefix = "${var.name}-${var.environment}"
  tags = {
    Application = var.name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

resource "aws_ecr_repository" "api" {
  name                 = "${local.prefix}-api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
  tags = local.tags
}

resource "aws_ecr_repository" "ui" {
  name                 = "${local.prefix}-ui"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "AES256" }
  tags = local.tags
}

resource "aws_secretsmanager_secret" "application" {
  name                    = "${local.prefix}/application"
  recovery_window_in_days = 7
  tags                    = local.tags
}

resource "aws_cloudwatch_log_group" "application" {
  name              = "/${var.name}/${var.environment}"
  retention_in_days = 30
  tags              = local.tags
}
