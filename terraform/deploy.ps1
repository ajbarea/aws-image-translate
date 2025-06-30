# Simplified Terraform deployment script for AWS Image Translation Pipeline (PowerShell)
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("init", "plan", "apply", "destroy", "output")]
    [string]$Action,

    [switch]$Help
)

function Show-Usage {
    Write-Host @"
Terraform deployment script for AWS Image Translation Pipeline

Usage: .\deploy-simple.ps1 -Action <ACTION>

Actions:
  init      Initialize Terraform
  plan      Plan infrastructure changes
  apply     Apply infrastructure changes
  destroy   Destroy all infrastructure
  output    Show Terraform outputs

Examples:
  .\deploy-simple.ps1 -Action init     # Initialize Terraform
  .\deploy-simple.ps1 -Action plan     # Plan changes
  .\deploy-simple.ps1 -Action apply    # Apply changes
  .\deploy-simple.ps1 -Action destroy  # Destroy infrastructure
"@
}

function Write-Log {
    param([string]$Message, [string]$Level = "INFO")

    $color = switch ($Level) {
        "INFO" { "Cyan" }
        "SUCCESS" { "Green" }
        "WARNING" { "Yellow" }
        "ERROR" { "Red" }
    }

    Write-Host "[$Level] $Message" -ForegroundColor $color
}

function Test-Requirements {
    # Check if terraform is installed
    try {
        $terraformPath = "C:\terraform\terraform.exe"
        if (Test-Path $terraformPath) {
            $version = & $terraformPath version 2>$null
            Write-Log "Terraform found: $($version.Split("`n")[0])" "SUCCESS"
        } else {
            Write-Log "Terraform not found at $terraformPath" "ERROR"
            exit 1
        }
    } catch {
        Write-Log "Error checking Terraform: $($_.Exception.Message)" "ERROR"
        exit 1
    }

    # Check if AWS CLI is configured
    try {
        $null = aws sts get-caller-identity 2>$null
        Write-Log "AWS CLI is configured" "SUCCESS"
    } catch {
        Write-Log "AWS CLI is not configured. Run 'aws configure' first." "ERROR"
        exit 1
    }

    # Check if terraform directory exists
    if (-not (Test-Path "terraform")) {
        Write-Log "Terraform directory not found" "ERROR"
        exit 1
    }

    # Check if terraform.tfvars exists
    if (-not (Test-Path "terraform\terraform.tfvars")) {
        Write-Log "terraform.tfvars not found. Make sure to create it and set your values." "WARNING"
    }
}

function Initialize-Terraform {
    Write-Log "Initializing Terraform..."
    Set-Location terraform
    & "C:\terraform\terraform.exe" init
    if ($LASTEXITCODE -eq 0) {
        Write-Log "Terraform initialized successfully" "SUCCESS"
    } else {
        Write-Log "Terraform initialization failed" "ERROR"
        exit 1
    }
}

function Invoke-TerraformPlan {
    Write-Log "Planning Terraform changes..."
    Set-Location terraform
    & "C:\terraform\terraform.exe" plan
}

function Invoke-TerraformApply {
    Write-Log "Applying Terraform changes..."
    Set-Location terraform
    & "C:\terraform\terraform.exe" apply

    if ($LASTEXITCODE -eq 0) {
        Write-Log "Infrastructure deployed successfully!" "SUCCESS"
        Write-Log "Run '.\deploy-simple.ps1 -Action output' to see the resource details." "INFO"
    }
}

function Invoke-TerraformDestroy {
    Write-Log "This will destroy ALL infrastructure!" "WARNING"
    $confirm = Read-Host "Are you sure you want to continue? (type 'yes' to confirm)"

    if ($confirm -ne "yes") {
        Write-Log "Deployment cancelled." "INFO"
        exit 0
    }

    Write-Log "Destroying Terraform infrastructure..."
    Set-Location terraform
    & "C:\terraform\terraform.exe" destroy

    if ($LASTEXITCODE -eq 0) {
        Write-Log "Infrastructure destroyed successfully!" "SUCCESS"
    }
}

function Show-TerraformOutputs {
    Write-Log "Terraform outputs:"
    Set-Location terraform
    & "C:\terraform\terraform.exe" output
}

# Main execution
if ($Help) {
    Show-Usage
    exit 0
}

Write-Log "AWS Image Translation Pipeline - Terraform Script"
Write-Log "Action: $Action"

# Check requirements for all actions except init
if ($Action -ne "init") {
    Test-Requirements
}

switch ($Action) {
    "init" { Initialize-Terraform }
    "plan" { Invoke-TerraformPlan }
    "apply" { Invoke-TerraformApply }
    "destroy" { Invoke-TerraformDestroy }
    "output" { Show-TerraformOutputs }
}
