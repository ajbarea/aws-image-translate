# AWS CodePipelines CI/CD
resource "aws_s3_bucket" "pipeline_artifacts" {
  count         = local.github_connection_arn != "" ? 1 : 0
  bucket        = "${var.project_name}-pipeline-artifacts-${var.environment}-${local.random_suffix}"
  force_destroy = true
}

resource "aws_cloudwatch_log_group" "codebuild_logs" {
  count             = local.github_connection_arn != "" ? 1 : 0
  name              = "/aws/codebuild/${var.project_name}-build-${var.environment}"
  retention_in_days = 14
  tags = {
    Name        = "${var.project_name}-codebuild-logs-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_iam_role" "codepipeline_role" {
  count = local.github_connection_arn != "" ? 1 : 0
  name  = "${var.project_name}-codepipeline-role-${var.environment}-${local.random_suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codepipeline.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "pipeline_admin" {
  count      = local.github_connection_arn != "" ? 1 : 0
  role       = aws_iam_role.codepipeline_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# Explicit CodeStar Connections permissions for CodePipeline
resource "aws_iam_role_policy" "codepipeline_codestar_policy" {
  count = local.github_connection_arn != "" ? 1 : 0

  name = "${var.project_name}-codepipeline-codestar-policy-${var.environment}-${local.random_suffix}"
  role = aws_iam_role.codepipeline_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "codestar-connections:UseConnection",
          "codestar-connections:GetConnection"
        ]
        Resource = local.github_connection_arn
      }
    ]
  })
}

resource "aws_iam_role" "codebuild_role" {
  count = local.github_connection_arn != "" ? 1 : 0
  name  = "${var.project_name}-codebuild-role-${var.environment}-${local.random_suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "codebuild.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "codebuild_admin" {
  count      = local.github_connection_arn != "" ? 1 : 0
  role       = aws_iam_role.codebuild_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}

# CodeBuild CloudWatch Logs policy
resource "aws_iam_role_policy" "codebuild_logs_policy" {
  count = local.github_connection_arn != "" ? 1 : 0
  name  = "${var.project_name}-codebuild-logs-policy-${var.environment}-${local.random_suffix}"
  role  = aws_iam_role.codebuild_role[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = [
          aws_cloudwatch_log_group.codebuild_logs[0].arn,
          "${aws_cloudwatch_log_group.codebuild_logs[0].arn}:*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "sts:GetCallerIdentity"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/google-oauth-*",
          "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:${var.project_name}/reddit-api-*"
        ]
      }
    ]
  })
}

resource "aws_codebuild_project" "lenslate_build" {
  count        = local.github_connection_arn != "" ? 1 : 0
  name         = "${var.project_name}-build-${var.environment}-${local.random_suffix}"
  service_role = aws_iam_role.codebuild_role[0].arn

  artifacts {
    type = "CODEPIPELINE"
  }

  environment {
    compute_type                = "BUILD_GENERAL1_SMALL"
    image                       = "aws/codebuild/standard:7.0"
    type                        = "LINUX_CONTAINER"
    privileged_mode             = true
    image_pull_credentials_type = "CODEBUILD"

    environment_variable {
      name  = "AWS_DEFAULT_REGION"
      value = "us-east-1"
    }

    environment_variable {
      name  = "AWS_REGION"
      value = "us-east-1"
    }

    environment_variable {
      name  = "PYTHONPATH"
      value = "/codebuild/output/src*/lambda_functions"
    }
  }

  source {
    type      = "CODEPIPELINE"
    buildspec = "buildspec.yml"
  }

  build_timeout = 30

  logs_config {
    cloudwatch_logs {
      status     = "ENABLED"
      group_name = aws_cloudwatch_log_group.codebuild_logs[0].name
    }
  }

  tags = {
    Name        = "${var.project_name}-build-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_codepipeline" "lenslate_pipeline" {
  for_each = local.github_connection_arn != "" ? toset(var.pipeline_branches) : toset([])

  name     = "${var.project_name}-pipeline-${each.key}-${var.environment}-${local.random_suffix}"
  role_arn = aws_iam_role.codepipeline_role[0].arn

  artifact_store {
    location = aws_s3_bucket.pipeline_artifacts[0].bucket
    type     = "S3"
  }

  tags = {
    Environment = var.environment
    Branch      = each.key
  }

  stage {
    name = "Source"

    action {
      name             = "Source"
      category         = "Source"
      owner            = "AWS"
      provider         = "CodeStarSourceConnection"
      version          = "1"
      output_artifacts = ["source_output"]

      configuration = {
        ConnectionArn    = local.github_connection_arn
        FullRepositoryId = "${var.github_owner}/${var.github_repo}"
        BranchName       = each.key
      }
    }
  }

  stage {
    name = "Build"

    action {
      name            = "Build"
      category        = "Build"
      owner           = "AWS"
      provider        = "CodeBuild"
      input_artifacts = ["source_output"]
      version         = "1"

      configuration = {
        ProjectName = aws_codebuild_project.lenslate_build[0].name
      }
    }
  }
}
