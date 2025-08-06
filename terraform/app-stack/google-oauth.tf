# Google OAuth integration configuration
locals {
  # Use OAuth credentials from oauth-automation.tf if available
  oauth_client_id     = try(local.final_google_client_id, var.google_oauth_client_id)
  oauth_client_secret = try(local.final_google_client_secret, var.google_oauth_client_secret)

  # OAuth URLs
  cloudfront_url     = "https://${aws_cloudfront_distribution.website.domain_name}"
  cognito_domain_url = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.region}.amazoncognito.com"
  oauth_redirect_uri = "${local.cognito_domain_url}/oauth2/idpresponse"

  # Local development origins (to get `python -m http.server` working)
  dev_origins = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3000",
    "http://127.0.0.1:3000"
  ]

  # File paths
  config_filename = "${path.module}/google-oauth-config.txt"
  script_filename = "${path.module}/update-google-oauth.sh"
  batch_filename  = "${path.module}/update-google-oauth.bat"
}

# Local file resource to generate Google OAuth configuration
resource "local_file" "google_oauth_config" {
  count = local.google_oauth_enabled ? 1 : 0

  filename = local.config_filename

  content = <<-EOT
# Google OAuth Configuration for Lenslate
# Generated automatically by Terraform

Client ID: ${local.oauth_client_id}

REQUIRED CONFIGURATION IN GOOGLE CLOUD CONSOLE:
===============================================

1. Go to: https://console.cloud.google.com/apis/credentials
2. Find OAuth 2.0 Client ID: ${local.oauth_client_id}
3. Click Edit and add these URLs:

AUTHORIZED JAVASCRIPT ORIGINS:
- ${local.cloudfront_url}
- ${local.cognito_domain_url}
%{for origin in local.dev_origins~}
- ${origin}
%{endfor~}

AUTHORIZED REDIRECT URIS:
- ${local.cloudfront_url}/
- ${local.oauth_redirect_uri}
%{for origin in local.dev_origins~}
- ${origin}/
%{endfor~}


CURRENT DEPLOYMENT URLS:
========================
CloudFront URL: ${local.cloudfront_url}
Cognito Domain: ${local.cognito_domain_url}
Redirect URI: ${local.oauth_redirect_uri}

Generated: ${timestamp()}
EOT

  lifecycle {
    create_before_destroy = true
  }
}

# Unix/Linux/Mac shell script
resource "local_file" "update_google_oauth_script" {
  count = local.google_oauth_enabled ? 1 : 0

  filename = local.script_filename

  content = <<-EOT
#!/bin/bash
# Google OAuth Configuration Script for Unix/Linux/Mac
set -e

echo "Updating Google OAuth configuration..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI not found. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check authentication
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -n1 > /dev/null; then
    echo "Please authenticate with Google Cloud:"
    gcloud auth login
fi

# Extract project ID
CLIENT_ID="${local.oauth_client_id}"
PROJECT_ID=$(echo "$CLIENT_ID" | cut -d'-' -f1)

echo "Client ID: $CLIENT_ID"
echo "Project ID: $PROJECT_ID"

gcloud config set project "$PROJECT_ID"

# Manual configuration required (gcloud OAuth updates are limited)
echo "WARNING: Automatic OAuth client updates are not fully supported by gcloud CLI"
echo "Please manually update the OAuth client in Google Cloud Console:"
echo ""
echo "Go to: https://console.cloud.google.com/apis/credentials"
echo "Find Client ID: $CLIENT_ID"
echo "Add these Authorized JavaScript origins:"
echo "   - ${local.cloudfront_url}"
echo "   - ${local.cognito_domain_url}"
echo ""
echo "Add this Authorized redirect URI:"
echo "   - ${local.oauth_redirect_uri}"
echo ""
echo "Configuration details saved to: google-oauth-config.txt"
echo ""
EOT

  lifecycle {
    create_before_destroy = true
  }
}

# Windows batch script
resource "local_file" "update_google_oauth_batch" {
  count = local.google_oauth_enabled ? 1 : 0

  filename = local.batch_filename

  content = <<-EOT
@echo off
REM Google OAuth Configuration Script for Windows
echo Updating Google OAuth configuration...

REM Check gcloud installation
where gcloud >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: gcloud CLI not found. Please install it first:
    echo    https://cloud.google.com/sdk/docs/install
    exit /b 1
)

REM Check authentication
for /f "tokens=*" %%i in ('gcloud auth list --filter=status:ACTIVE --format="value(account)" 2^>nul') do set ACTIVE_ACCOUNT=%%i
if "%ACTIVE_ACCOUNT%"=="" (
    echo Please authenticate with Google Cloud:
    gcloud auth login
)

set CLIENT_ID=${local.oauth_client_id}
echo Client ID: %CLIENT_ID%

REM Manual configuration required (gcloud OAuth updates are limited)
echo WARNING: Automatic OAuth client updates are not fully supported by gcloud CLI
echo Please manually update the OAuth client in Google Cloud Console:
echo.
echo Go to: https://console.cloud.google.com/apis/credentials
echo Find Client ID: %CLIENT_ID%
echo Add these Authorized JavaScript origins:
echo    - ${local.cloudfront_url}
echo    - ${local.cognito_domain_url}
echo.
echo Add this Authorized redirect URI:
echo    - ${local.oauth_redirect_uri}
echo.
echo Configuration details saved to: google-oauth-config.txt
EOT

  lifecycle {
    create_before_destroy = true
  }
}

# Null resource to run post-deployment script
resource "null_resource" "google_oauth_post_deploy" {
  count = local.google_oauth_enabled ? 1 : 0

  triggers = {
    cloudfront_domain = aws_cloudfront_distribution.website.domain_name
    cognito_domain    = aws_cognito_user_pool_domain.main.domain
    client_id         = local.oauth_client_id
    config_file       = local_file.google_oauth_config[0].id
    script_file       = local_file.update_google_oauth_script[0].id
    batch_file        = local_file.update_google_oauth_batch[0].id
    timestamp         = timestamp()
  }

  provisioner "local-exec" {
    command     = "python post_deploy_message.py \"${local.cloudfront_url}\" \"${local.cognito_domain_url}\""
    working_dir = path.module
  }

  depends_on = [
    local_file.google_oauth_config,
    local_file.update_google_oauth_script,
    local_file.update_google_oauth_batch
  ]
}
