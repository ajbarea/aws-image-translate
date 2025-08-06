# Google OAuth automation for turnkey deployment

# Data source to read OAuth credentials from AWS Secrets Manager
data "aws_secretsmanager_secret" "google_oauth" {
  count = var.use_secrets_manager_oauth ? 1 : 0
  name  = "/${var.project_name}/${var.environment}/google-oauth"
}

data "aws_secretsmanager_secret_version" "google_oauth" {
  count     = var.use_secrets_manager_oauth ? 1 : 0
  secret_id = data.aws_secretsmanager_secret.google_oauth[0].id
}

# Local values that choose between Secrets Manager or .env.local
locals {
  # Parse the JSON secret if Secrets Manager is enabled
  oauth_secret_json = var.use_secrets_manager_oauth && length(data.aws_secretsmanager_secret_version.google_oauth) > 0 ? jsondecode(data.aws_secretsmanager_secret_version.google_oauth[0].secret_string) : {}

  # Try Secrets Manager first, then fall back to .env.local, then variables
  final_google_client_id = var.use_secrets_manager_oauth && contains(keys(local.oauth_secret_json), "client_id") ? local.oauth_secret_json.client_id : var.google_oauth_client_id

  final_google_client_secret = var.use_secrets_manager_oauth && contains(keys(local.oauth_secret_json), "client_secret") ? local.oauth_secret_json.client_secret : var.google_oauth_client_secret

  # Update the google_oauth_enabled check to use final values
  google_oauth_enabled = local.final_google_client_id != "" && local.final_google_client_id != "placeholder_client_id"
}

# Output to help teams set up Secrets Manager
output "oauth_secrets_manager_setup" {
  value = var.use_secrets_manager_oauth ? {
    setup_commands = [
      "# Run this command to set up centralized OAuth credentials:",
      "aws secretsmanager create-secret \\",
      "  --name '/${var.project_name}/${var.environment}/google-oauth' \\",
      "  --description 'Google OAuth credentials for ${var.project_name} ${var.environment}' \\",
      "  --secret-string '{\"client_id\":\"YOUR_GOOGLE_CLIENT_ID\",\"client_secret\":\"YOUR_GOOGLE_CLIENT_SECRET\"}'",
      "",
      "# After setup, all developers can deploy without sharing secrets!",
      "# They just need AWS credentials and can run: python deploy.py"
    ]
    secret_name = "/${var.project_name}/${var.environment}/google-oauth"
    console_url = "https://console.aws.amazon.com/secretsmanager/home?region=${var.region}#/secret?name=${urlencode("/${var.project_name}/${var.environment}/google-oauth")}"
    message     = "Secrets Manager OAuth is enabled."
    } : {
    setup_commands = ["# Secrets Manager OAuth is disabled. Using .env.local method."]
    secret_name    = ""
    console_url    = ""
    message        = "Secrets Manager OAuth is disabled. Using .env.local method."
  }
}

# Post-deployment message for Secrets Manager setup
resource "local_file" "turnkey_oauth_setup" {
  count = !local.google_oauth_enabled && var.use_secrets_manager_oauth ? 1 : 0

  filename = "${path.module}/turnkey-oauth-setup.md"

  content = <<-EOT
# Turnkey Google OAuth Setup with AWS Secrets Manager

## One-Time Team Setup (Team Lead Only)

### 1. Create Google OAuth Client
- Go to: https://console.cloud.google.com/apis/credentials
- Create OAuth 2.0 Client ID
- Note the Client ID and Secret

### 2. Store in AWS Secrets Manager (Recommended)
```bash
aws secretsmanager create-secret \
  --name "/${var.project_name}/${var.environment}/google-oauth" \
  --description "Google OAuth credentials for ${var.project_name} ${var.environment}" \
  --secret-string '{"client_id":"YOUR_GOOGLE_CLIENT_ID","client_secret":"YOUR_GOOGLE_CLIENT_SECRET"}'
```

**Why Secrets Manager vs Parameter Store?**
- ✅ Automatic rotation capability
- ✅ Better audit logging and access control
- ✅ Cross-region replication
- ✅ Versioning and rollback
- ✅ JSON structure for related secrets

### 3. Configure OAuth Client in Google Console
After deployment, use the generated URLs:
- Authorized JavaScript Origins: ${local.cloudfront_url}
- Authorized Redirect URIs: ${local.oauth_redirect_uri}

### 4. Enable Secrets Manager in Terraform
Set this variable in your deployment:
```bash
export TF_VAR_use_secrets_manager_oauth=true
```

## Developer Experience After Setup

Developers just need:
```bash
git clone <repository>
aws configure  # Only AWS credentials needed
export TF_VAR_use_secrets_manager_oauth=true
python deploy.py
```

**No secrets to share!** OAuth credentials are automatically pulled from Secrets Manager.

## Security Benefits
- 🔒 Centralized secret management
- 📊 Audit trail of secret access
- 🔄 Automatic rotation (future capability)
- 🌍 Cross-region disaster recovery
- 👥 Fine-grained team access controls

Generated: ${timestamp()}
EOT
}
