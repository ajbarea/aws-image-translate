# Python Virtual Environment Setup Script for AWS Image Translation Pipeline (PowerShell)

param(
    [switch]$Dev = $true,
    [switch]$Prod,
    [switch]$Clean,
    [switch]$Help
)

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

function Show-Usage {
    Write-Host @"
Python Virtual Environment Setup Script

Usage: .\setup-env.ps1 [OPTIONS]

Options:
  -Dev          Install development dependencies (default)
  -Prod         Install production dependencies only
  -Clean        Remove existing virtual environment first
  -Help         Show this help message

Examples:
  .\setup-env.ps1                 # Setup with dev dependencies
  .\setup-env.ps1 -Prod           # Setup with production dependencies only
  .\setup-env.ps1 -Clean -Dev     # Clean setup with dev dependencies
"@
}

# Handle help request
if ($Help) {
    Show-Usage
    exit 0
}

# Handle prod flag (overrides dev)
if ($Prod) {
    $Dev = $false
}

$VenvDir = ".venv"

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Log "Using $pythonVersion" "SUCCESS"
} catch {
    Write-Log "Python is not installed or not in PATH" "ERROR"
    exit 1
}

# Clean existing virtual environment if requested
if ($Clean -and (Test-Path $VenvDir)) {
    Write-Log "Removing existing virtual environment..." "WARNING"
    Remove-Item -Recurse -Force $VenvDir
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path $VenvDir)) {
    Write-Log "Creating virtual environment..."
    python -m venv $VenvDir
    Write-Log "Virtual environment created successfully" "SUCCESS"
} else {
    Write-Log "Virtual environment already exists"
}

# Determine activation script path
$activateScript = Join-Path $VenvDir "Scripts\Activate.ps1"

# Check if activation script exists
if (-not (Test-Path $activateScript)) {
    Write-Log "Virtual environment activation script not found: $activateScript" "ERROR"
    exit 1
}

# Activate virtual environment
Write-Log "Activating virtual environment..."
& $activateScript

# Upgrade pip
Write-Log "Upgrading pip..."
python -m pip install --upgrade pip

# Install dependencies
if ($Dev) {
    if (Test-Path "requirements-dev.txt") {
        Write-Log "Installing development dependencies..."
        pip install -r requirements-dev.txt
        Write-Log "Development dependencies installed successfully" "SUCCESS"
    } else {
        Write-Log "requirements-dev.txt not found, installing base requirements only" "WARNING"
        if (Test-Path "requirements.txt") {
            pip install -r requirements.txt
        } else {
            Write-Log "No requirements files found" "ERROR"
            exit 1
        }
    }
} else {
    if (Test-Path "requirements.txt") {
        Write-Log "Installing production dependencies..."
        pip install -r requirements.txt
        Write-Log "Production dependencies installed successfully" "SUCCESS"
    } else {
        Write-Log "requirements.txt not found" "ERROR"
        exit 1
    }
}

Write-Log "Environment setup complete!" "SUCCESS"
Write-Log "To activate the virtual environment in the future, run:"
Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor Yellow
