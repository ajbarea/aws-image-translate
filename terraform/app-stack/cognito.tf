resource "aws_cognito_user_pool" "pool" {
  name = "${var.project_name}-user-pool-${var.environment}-${local.random_suffix}"

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  auto_verified_attributes = ["email"]

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
  }

  lambda_config {
    custom_message = aws_lambda_function.cognito_triggers.arn
    pre_sign_up    = aws_lambda_function.cognito_triggers.arn
  }

  depends_on = [aws_lambda_function.cognito_triggers]
}

resource "aws_cognito_user_pool_client" "client" {
  name                = "${var.project_name}-client-${var.environment}-${local.random_suffix}"
  user_pool_id        = aws_cognito_user_pool.pool.id
  generate_secret     = false
  explicit_auth_flows = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_PASSWORD_AUTH"]

  supported_identity_providers = var.google_oauth_client_id != "" && var.google_oauth_client_id != "placeholder_client_id" ? ["COGNITO", "Google"] : ["COGNITO"]

  callback_urls = [
    "https://${aws_cloudfront_distribution.website.domain_name}/",
    "https://${local.frontend_bucket_name}.s3-website-${var.region}.amazonaws.com/"
  ]

  logout_urls = [
    "https://${aws_cloudfront_distribution.website.domain_name}/auth/logout",
    "https://${local.frontend_bucket_name}.s3-website-${var.region}.amazonaws.com/auth/logout"
  ]

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "profile", "email", "aws.cognito.signin.user.admin"]
  allowed_oauth_flows_user_pool_client = true

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }

  access_token_validity  = var.cognito_access_token_validity
  id_token_validity      = var.cognito_id_token_validity
  refresh_token_validity = var.cognito_refresh_token_validity

  prevent_user_existence_errors = "ENABLED"

  read_attributes = [
    "email",
    "email_verified",
    "name",
    "preferred_username",
    "given_name",
    "family_name"
  ]

  write_attributes = [
    "email",
    "name",
    "preferred_username",
    "given_name",
    "family_name"
  ]
}

resource "aws_cognito_identity_pool" "main" {
  identity_pool_name               = "${var.project_name}-identity-pool-${var.environment}-${local.random_suffix}"
  allow_unauthenticated_identities = false

  cognito_identity_providers {
    client_id     = aws_cognito_user_pool_client.client.id
    provider_name = aws_cognito_user_pool.pool.endpoint
  }
}

resource "aws_iam_role" "authenticated" {
  name = "${var.project_name}-cognito-authenticated-${var.environment}-${local.random_suffix}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = "cognito-identity.amazonaws.com"
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "cognito-identity.amazonaws.com:aud" = aws_cognito_identity_pool.main.id
          }
          "ForAnyValue:StringLike" = {
            "cognito-identity.amazonaws.com:amr" = "authenticated"
          }
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "authenticated_policy" {
  name = "${var.project_name}-cognito-authenticated-policy-${var.environment}-${local.random_suffix}"
  role = aws_iam_role.authenticated.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject", "s3:ListBucket"]
        Resource = [aws_s3_bucket.image_storage.arn, "${aws_s3_bucket.image_storage.arn}/*"]
      }
    ]
  })
}

resource "aws_cognito_identity_pool_roles_attachment" "main" {
  identity_pool_id = aws_cognito_identity_pool.main.id

  roles = {
    "authenticated" = aws_iam_role.authenticated.arn
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-auth-${var.environment}-${local.random_suffix}"
  user_pool_id = aws_cognito_user_pool.pool.id
}

resource "aws_cognito_identity_provider" "google" {
  count = var.google_oauth_client_id != "" && var.google_oauth_client_id != "placeholder_client_id" ? 1 : 0

  user_pool_id  = aws_cognito_user_pool.pool.id
  provider_name = "Google"
  provider_type = "Google"

  provider_details = {
    client_id        = var.google_oauth_client_id
    client_secret    = var.google_oauth_client_secret
    authorize_scopes = "openid profile email"
  }

  attribute_mapping = {
    email       = "email"
    name        = "name"
    username    = "sub"
    given_name  = "given_name"
    family_name = "family_name"
  }

  depends_on = [aws_cognito_user_pool.pool]
}
